from datetime import datetime, timezone, timedelta

from banker_radar.models import BacktestSummary, SignalTrackingRecord
from banker_radar.tracking.direction import infer_signal_direction
from banker_radar.tracking.performance import calculate_performance


def test_infer_signal_direction_records_source():
    decision = infer_signal_direction("综合异动", {"direction": "short"})
    assert decision.direction == "short"
    assert decision.source == "metadata_override"

    assert infer_signal_direction("空头燃料").direction == "long"
    neutral = infer_signal_direction("综合异动")
    assert neutral.direction == "neutral"
    assert neutral.source == "neutral_default"


def test_tracking_record_due_detection_and_metadata_defaults():
    ts = datetime(2026, 4, 24, 8, 0, tzinfo=timezone.utc)
    record = SignalTrackingRecord(
        signal_id=1,
        symbol="KATUSDT",
        kind="空头燃料",
        source="binance",
        direction="long",
        signal_ts=ts,
        entry_price=1.0,
        window_minutes=15,
        due_ts=ts + timedelta(minutes=15),
    )
    assert record.status == "pending"
    assert record.is_due(ts + timedelta(minutes=16))
    assert record.metadata == {}


def test_backtest_summary_win_rate_excludes_neutral_and_marks_low_sample():
    summary = BacktestSummary(kind="空头燃料", window_minutes=60, total=4, directional_total=3, wins=2, avg_return_pct=2.5, min_samples=5)
    assert round(summary.win_rate_pct, 2) == 66.67
    assert summary.sample_warning == "样本不足"


def test_long_short_and_neutral_performance_with_outlier_flag():
    long_p = calculate_performance("long", entry=100, observed=110, high=115, low=96, success_threshold_pct=2, outlier_return_pct=80)
    assert round(long_p["return_pct"], 2) == 10.0
    assert round(long_p["max_runup_pct"], 2) == 15.0
    assert round(long_p["max_drawdown_pct"], 2) == -4.0
    assert long_p["success"] is True

    short_p = calculate_performance("short", entry=100, observed=90, high=108, low=85, success_threshold_pct=2, outlier_return_pct=80)
    assert round(short_p["return_pct"], 2) == 10.0
    assert round(short_p["max_runup_pct"], 2) == 15.0
    assert round(short_p["max_drawdown_pct"], 2) == -8.0
    assert short_p["success"] is True

    neutral_p = calculate_performance("neutral", entry=100, observed=190, high=195, low=90, success_threshold_pct=2, outlier_return_pct=80)
    assert neutral_p["success"] is None
    assert neutral_p["is_outlier"] is True
