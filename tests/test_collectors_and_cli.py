from banker_radar.collectors.binance_futures import parse_binance_candles, merge_binance_features
from banker_radar.models import Candle, MarketFeature


def test_parse_binance_candles_converts_quote_volume_to_candle_volume_usd():
    raw = [[1700000000000, "10", "11", "9", "10.5", "100", 1700000100000, "1050", 1, "0", "0", "0"]]

    candles = parse_binance_candles(raw)

    assert candles == [Candle(ts=1700000000000, open=10.0, high=11.0, low=9.0, close=10.5, volume_usd=1050.0)]


def test_merge_binance_features_uses_ticker_oi_and_funding_rows():
    tickers = [{"symbol": "SAGAUSDT", "priceChangePercent": "0.8", "quoteVolume": "5000000"}]
    oi = {"symbol": "SAGAUSDT", "sumOpenInterestValue": "8000000", "sumOpenInterestValueDeltaPct": "4.2"}
    funding = [{"symbol": "SAGAUSDT", "lastFundingRate": "-0.0001"}]

    features = merge_binance_features(tickers, [oi], funding)

    assert features == [MarketFeature(symbol="SAGAUSDT", price_change_pct=0.8, oi_delta_pct=4.2, funding_rate_pct=-0.01, volume_usd_24h=5000000.0, oi_usd=8000000.0, source="binance")]
