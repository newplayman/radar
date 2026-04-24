from datetime import datetime, timezone

import pytest

from banker_radar.collectors.price_observer import KlineCache, RequestBudget, parse_klines_observation


def test_parse_klines_observation_calculates_close_high_low_and_times():
    rows = [
        [1000, "100", "105", "98", "102", "0", 1999, "0"],
        [2000, "102", "110", "101", "108", "0", 2999, "0"],
    ]
    obs = parse_klines_observation("KATUSDT", rows, provider="binance", interval="15m")
    assert obs.observed_price == 108
    assert obs.high_price == 110
    assert obs.low_price == 98
    assert obs.kline_count == 2
    assert obs.observation_start_ts == datetime.fromtimestamp(1, tz=timezone.utc)
    assert obs.observation_end_ts == datetime.fromtimestamp(2.999, tz=timezone.utc)


def test_request_budget_tracks_total_and_provider_limits():
    budget = RequestBudget(max_requests=2, max_requests_per_provider=1)
    assert budget.consume("binance") is True
    assert budget.consume("binance") is False
    assert budget.consume("okx") is True
    assert budget.consume("gmgn") is False


def test_kline_cache_reuses_same_symbol_provider_interval_request():
    calls = []

    def fetcher(symbol, start_ms, end_ms, interval):
        calls.append((symbol, interval))
        return [[start_ms, "1", "2", "0.5", "1.5", "0", end_ms, "0"]]

    cache = KlineCache()
    a = cache.get("binance", "ABCUSDT", "15m", 1, 2, fetcher)
    b = cache.get("binance", "ABCUSDT", "15m", 1, 2, fetcher)
    assert a == b
    assert calls == [("ABCUSDT", "15m")]


def test_parse_klines_observation_rejects_empty_rows():
    with pytest.raises(ValueError, match="no_klines"):
        parse_klines_observation("BADUSDT", [], provider="binance")
