from banker_radar.models import AccumulationResult, MarketFeature
from banker_radar.signals.scoring import score_market


def test_dark_flow_signal_scores_high_when_oi_rises_but_price_flat_in_pool():
    feature = MarketFeature(symbol="SAGAUSDT", price_change_pct=0.8, oi_delta_pct=4.2, funding_rate_pct=-0.01, volume_usd_24h=5_000_000, oi_usd=8_000_000)
    acc = AccumulationResult(symbol="SAGAUSDT", in_pool=True, sideways_days=77, range_pct=18, avg_volume_usd=2_000_000, slope_pct=1.0, score=85)

    signal = score_market(feature, acc)

    assert signal.kind == "暗流吸筹"
    assert signal.score >= 75
    assert "OI" in signal.reason


def test_short_fuel_signal_for_positive_price_and_negative_funding():
    feature = MarketFeature(symbol="REDUSDT", price_change_pct=8.5, oi_delta_pct=2.5, funding_rate_pct=-0.08, volume_usd_24h=12_000_000, oi_usd=20_000_000)

    signal = score_market(feature, None)

    assert signal.kind == "空头燃料"
    assert signal.score >= 60
