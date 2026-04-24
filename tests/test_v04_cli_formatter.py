from datetime import datetime, timezone

from banker_radar.alerts.formatter import format_backtest_report
from banker_radar.cli import _parse_windows, build_parser
from banker_radar.models import BacktestSummary


def test_cli_accepts_v04_commands_and_force_flag():
    parser = build_parser()
    args = parser.parse_args(["track-signals", "--db", "x.db"])
    assert args.command == "track-signals"
    args = parser.parse_args(["telegram-review", "--period", "yesterday", "--force", "--dry-run"])
    assert args.command == "telegram-review"
    assert args.force is True


def test_format_backtest_report_includes_risk_disclaimer_low_sample_and_drawdown():
    text = format_backtest_report(
        [BacktestSummary(kind="空头燃料", window_minutes=60, total=3, directional_total=3, wins=2, avg_return_pct=4.2, avg_max_drawdown_pct=-3.1, min_samples=5)],
        title="庄家雷达 每日复盘",
        period_label="昨日",
    )
    assert "庄家雷达 每日复盘" in text
    assert "样本不足" in text
    assert "平均回撤" in text
    assert "未计滑点/手续费/真实成交" in text


def test_parse_windows_accepts_yaml_list_or_comma_string():
    assert _parse_windows([15, "60", 240]) == [15, 60, 240]
    assert _parse_windows("15, 60,240") == [15, 60, 240]
