from banker_radar.models import Candle
from banker_radar.engines.accumulation import analyze_accumulation


def make_candles(days=60, base=10.0, width=0.2, vol=1_000_000):
    return [
        Candle(ts=i, open=base, high=base + width, low=base - width, close=base + ((i % 3) - 1) * 0.02, volume_usd=vol)
        for i in range(days)
    ]


def test_sideways_low_volume_market_enters_accumulation_pool():
    result = analyze_accumulation("SAGAUSDT", make_candles(days=60), min_sideways_days=45, max_range_pct=80, max_avg_vol_usd=20_000_000)

    assert result.in_pool is True
    assert result.sideways_days == 60
    assert result.score >= 70


def test_trending_wide_range_market_is_rejected():
    candles = [Candle(ts=i, open=i+1, high=i+3, low=i, close=i+2, volume_usd=1_000_000) for i in range(60)]

    result = analyze_accumulation("HOTUSDT", candles, min_sideways_days=45, max_range_pct=80, max_avg_vol_usd=20_000_000)

    assert result.in_pool is False
    assert result.score < 70
