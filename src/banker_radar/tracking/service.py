from __future__ import annotations

from datetime import datetime, timedelta, timezone

from banker_radar.collectors.price_observer import KlineCache, RequestBudget, classify_price_error, observe_binance_window
from banker_radar.models import SignalTrackingRecord
from banker_radar.tracking.performance import calculate_performance


def enqueue_tracking_for_recent_signals(store, windows_minutes: list[int], *, since_hours: int = 48, limit: int = 500) -> int:
    return store.enqueue_tracking(windows_minutes, since=datetime.now(timezone.utc) - timedelta(hours=since_hours), limit=limit)


def process_due_tracking(store, *, now: datetime | None = None, limit: int = 50, success_threshold_pct: float = 2.0, outlier_return_pct: float = 80.0, interval: str = "15m", request_budget: RequestBudget | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cache = KlineCache()
    stats = {"processed": 0, "completed": 0, "failed_retryable": 0, "failed_permanent": 0, "skipped_no_entry": 0, "skipped_provider_blocked": 0}
    if hasattr(store, "is_provider_blocked") and store.is_provider_blocked("binance", now):
        stats["skipped_provider_blocked"] = 1
        return stats
    records = store.due_tracking_records(now=now, limit=limit)
    for record in records:
        stats["processed"] += 1
        if record.entry_price <= 0:
            # v0.4 hardening: do not loop forever if no entry price was captured.
            store.fail_tracking(record, status="failed_permanent", error="missing_entry_price")
            stats["skipped_no_entry"] += 1
            stats["failed_permanent"] += 1
            continue
        try:
            start_ms = int(record.signal_ts.timestamp() * 1000)
            end_ms = int(record.due_ts.timestamp() * 1000)
            obs = observe_binance_window(record.symbol, start_ms, end_ms, interval=interval, budget=request_budget, cache=cache)
            perf = calculate_performance(record.direction, entry=record.entry_price, observed=obs.observed_price, high=obs.high_price, low=obs.low_price, success_threshold_pct=success_threshold_pct, outlier_return_pct=outlier_return_pct)
            store.complete_tracking(
                record,
                observed_price=obs.observed_price,
                high_price=obs.high_price,
                low_price=obs.low_price,
                return_pct=perf["return_pct"],
                max_runup_pct=perf["max_runup_pct"],
                max_drawdown_pct=perf["max_drawdown_pct"],
                success=perf["success"],
                metadata={"is_outlier": perf["is_outlier"], "price_provider": obs.provider},
                observation_start_ts=obs.observation_start_ts,
                observation_end_ts=obs.observation_end_ts,
                price_provider=obs.provider,
                provider_interval=obs.interval,
            )
            stats["completed"] += 1
        except Exception as exc:
            reason = classify_price_error(exc)
            if reason == "rate_limited":
                store.set_provider_cooldown("binance", now + timedelta(minutes=15), reason=reason, retry_count=record.retry_count + 1)
            permanent = reason in {"symbol_not_found", "no_klines"} or record.retry_count >= 3
            status = "failed_permanent" if permanent else "failed_retryable"
            store.fail_tracking(record, status=status, error=reason)
            stats[status] += 1
    return stats


def summarize_completed_tracking(store, *, period: str = "yesterday", now: datetime | None = None, min_samples: int = 5):
    start, end, _ = resolve_period(period, now=now)
    return store.backtest_summaries(period_start=start, period_end=end, min_samples=min_samples)


def resolve_period(period: str, *, now: datetime | None = None) -> tuple[datetime, datetime, str]:
    now = now or datetime.now(timezone.utc)
    today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    if period == "today":
        return today, now, "今日"
    if period == "yesterday":
        return today - timedelta(days=1), today, "昨日"
    if period == "7d":
        return now - timedelta(days=7), now, "近7天"
    raise ValueError(f"unsupported_period:{period}")
