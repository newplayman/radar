from banker_radar.models import RadarSignal
from banker_radar.storage.sqlite import RadarStore
from banker_radar.alerts.formatter import format_report


def test_store_saves_and_loads_latest_signals(tmp_path):
    db = RadarStore(tmp_path / "radar.db")
    db.init()
    db.save_signal(RadarSignal(symbol="SAGAUSDT", kind="暗流吸筹", score=82, reason="OI +4.2%, price flat", risk="中", source="test"))

    rows = db.latest_signals(limit=5)

    assert len(rows) == 1
    assert rows[0].symbol == "SAGAUSDT"
    assert rows[0].kind == "暗流吸筹"


def test_format_report_groups_signals_for_telegram():
    text = format_report([
        RadarSignal(symbol="SAGAUSDT", kind="暗流吸筹", score=82, reason="OI +4.2%, 价格 +0.8%", risk="中", source="okx+binance"),
        RadarSignal(symbol="REDUSDT", kind="空头燃料", score=76, reason="费率 -0.08%, 价格 +8.5%", risk="高", source="binance"),
    ], title="庄家雷达 v0.1 测试")

    assert "🏦 庄家雷达 v0.1 测试" in text
    assert "🎯 暗流/埋伏榜" in text
    assert "🔥 轧空/追多榜" in text
    assert "非投资建议" in text
