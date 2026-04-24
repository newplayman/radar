import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from banker_radar.models import RadarSignal, SignalTrackingRecord
from banker_radar.storage.sqlite import RadarStore
from banker_radar.tracking.service import enqueue_tracking_for_recent_signals, process_due_tracking, summarize_completed_tracking


def _signal(symbol="ABCUSDT", kind="空头燃料", metadata=None, source="binance"):
    return RadarSignal(symbol=symbol, kind=kind, score=80, reason="reason", risk="中", source=source, created_at="2026-04-24T08:00:00+00:00", metadata=metadata or {})


def test_sqlite_tracking_schema_enqueue_is_idempotent_and_copies_risk_metadata(tmp_path: Path):
    store = RadarStore(tmp_path / "radar.db")
    store.init()
    store.save_signal(_signal(metadata={"price": 1.23}))

    count1 = store.enqueue_tracking(windows_minutes=[15, 60])
    count2 = store.enqueue_tracking(windows_minutes=[15, 60])

    assert count1 == 2
    assert count2 == 0
    due = store.due_tracking_records(now=datetime(2026, 4, 24, 9, 1, tzinfo=timezone.utc), limit=10)
    assert {r.window_minutes for r in due} == {15, 60}
    assert due[0].metadata["risk"] == "中"
    assert due[0].metadata["score"] == 80


def test_sqlite_complete_tracking_and_backtest_summary_excludes_neutral(tmp_path: Path):
    store = RadarStore(tmp_path / "radar.db")
    store.init()
    store.save_signal(_signal(kind="空头燃料"))
    store.save_signal(_signal(symbol="XYZUSDT", kind="综合异动"))
    store.enqueue_tracking(windows_minutes=[15])
    due = store.due_tracking_records(now=datetime(2026, 4, 24, 8, 20, tzinfo=timezone.utc), limit=10)
    for r in due:
        store.complete_tracking(r, observed_price=110, high_price=115, low_price=95, return_pct=10, max_runup_pct=15, max_drawdown_pct=-5, success=(None if r.direction == "neutral" else True), metadata={"price_provider": "binance"})

    summaries = store.backtest_summaries(period_start=datetime(2026, 4, 24, tzinfo=timezone.utc), period_end=datetime(2026, 4, 25, tzinfo=timezone.utc), min_samples=5)
    by_kind = {s.kind: s for s in summaries}
    assert by_kind["空头燃料"].wins == 1
    assert by_kind["综合异动"].directional_total == 0
    assert by_kind["综合异动"].win_rate_pct == 0


def test_provider_cooldown_and_review_send_idempotency(tmp_path: Path):
    store = RadarStore(tmp_path / "radar.db")
    store.init()
    now = datetime(2026, 4, 24, 8, 0, tzinfo=timezone.utc)
    assert not store.is_provider_blocked("binance", now)
    store.set_provider_cooldown("binance", now + timedelta(minutes=15), reason="rate_limited", retry_count=2)
    assert store.is_provider_blocked("binance", now + timedelta(minutes=1))
    assert not store.is_provider_blocked("binance", now + timedelta(minutes=16))

    assert store.record_review_send(now, now + timedelta(days=1), "telegram", "hash1") is True
    assert store.record_review_send(now, now + timedelta(days=1), "telegram", "hash1") is False
    assert store.record_review_send(now, now + timedelta(days=1), "telegram", "hash2", force=True) is True


def test_tracking_service_enqueues_and_summarizes(tmp_path: Path):
    store = RadarStore(tmp_path / "radar.db")
    store.init()
    store.save_signal(_signal())
    assert enqueue_tracking_for_recent_signals(store, [15]) == 1
    assert summarize_completed_tracking(store, period="today") == []


def test_tracking_service_respects_persistent_provider_cooldown_before_claiming_due_records(tmp_path: Path):
    store = RadarStore(tmp_path / "radar.db")
    store.init()
    store.save_signal(_signal(metadata={"price": 1.0}))
    store.enqueue_tracking(windows_minutes=[15])
    now = datetime(2026, 4, 24, 8, 20, tzinfo=timezone.utc)
    store.set_provider_cooldown("binance", now + timedelta(minutes=15), reason="rate_limited")

    stats = process_due_tracking(store, now=now, limit=10)

    assert stats["processed"] == 0
    assert stats["skipped_provider_blocked"] == 1
    # The pending record was not claimed into in_progress, so it can be processed next cycle.
    assert len(store.due_tracking_records(now=now + timedelta(minutes=16), limit=10)) == 1


def test_tracking_service_backfills_missing_entry_price_for_okx_symbol(tmp_path: Path, monkeypatch):
    store = RadarStore(tmp_path / "radar.db")
    store.init()
    store.save_signal(_signal(symbol="INJ-USDT-SWAP", source="okx", metadata={}))
    store.enqueue_tracking(windows_minutes=[15])

    def fake_observe(symbol, start_ms, end_ms, interval="15m", budget=None, cache=None):
        assert symbol == "INJUSDT"
        from banker_radar.collectors.price_observer import PriceObservation
        return PriceObservation(symbol=symbol, entry_price=100, observed_price=106, high_price=108, low_price=99, provider="binance", interval=interval)

    monkeypatch.setattr("banker_radar.tracking.service.observe_binance_window", fake_observe)
    stats = process_due_tracking(store, now=datetime(2026, 4, 24, 8, 20, tzinfo=timezone.utc), limit=10)

    assert stats["completed"] == 1
    summaries = store.backtest_summaries(period_start=datetime(2026, 4, 24, tzinfo=timezone.utc), period_end=datetime(2026, 4, 25, tzinfo=timezone.utc), min_samples=1)
    assert summaries[0].avg_return_pct == 6
