from banker_radar.alerts.formatter import format_report
from banker_radar.models import RadarSignal
from banker_radar.cli import build_parser


def test_formatter_prioritizes_resonance_and_smart_money_sections():
    report = format_report(
        [
            RadarSignal("AAAUSDT", "综合异动", 70, "综合", "中", "okx"),
            RadarSignal("BBBUSDT", "链上聪明钱", 80, "聪明钱买入", "中", "gmgn"),
            RadarSignal("CCCUSDT", "链上链下共振", 90, "共振", "中高", "gmgn+okx"),
        ],
        title="庄家雷达 v0.3 扫描",
    )

    assert "🧬 链上链下共振榜" in report
    assert "🧠 链上聪明钱榜" in report
    assert report.index("🧬 链上链下共振榜") < report.index("🧠 链上聪明钱榜") < report.index("📊 综合异动榜")


def test_cli_accepts_no_smart_money_flag():
    parser = build_parser()
    args = parser.parse_args(["scan", "--no-smart-money"])
    assert args.no_smart_money is True
