from __future__ import annotations

import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from banker_radar.collectors.binance_futures import fetch_json


@dataclass(frozen=True)
class PriceObservation:
    symbol: str
    observed_price: float
    high_price: float
    low_price: float
    provider: str
    interval: str = "15m"
    kline_count: int = 0
    observation_start_ts: datetime | None = None
    observation_end_ts: datetime | None = None
    # First close price inside the observation window. Used to backfill legacy
    # v0.1-v0.3 signals that did not store an entry price.
    entry_price: float | None = None


def normalize_binance_symbol(symbol: str) -> str:
    """Convert common exchange-specific contract symbols to Binance futures form.

    Examples:
    - INJ-USDT-SWAP -> INJUSDT
    - BTCUSDT -> BTCUSDT
    """
    value = symbol.strip().upper()
    if value.endswith("-USDT-SWAP"):
        return value.replace("-USDT-SWAP", "USDT")
    return value.replace("-", "") if "-" in value and value.endswith("USDT") else value


@dataclass
class RequestBudget:
    max_requests: int
    max_requests_per_provider: int | None = None
    used: int = 0
    provider_used: dict[str, int] = field(default_factory=dict)

    def consume(self, provider: str) -> bool:
        if self.used >= self.max_requests:
            return False
        if self.max_requests_per_provider is not None and self.provider_used.get(provider, 0) >= self.max_requests_per_provider:
            return False
        self.used += 1
        self.provider_used[provider] = self.provider_used.get(provider, 0) + 1
        return True


class KlineCache:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, str, str], list[list]] = {}

    def get(self, provider: str, symbol: str, interval: str, start_ms: int, end_ms: int, fetcher: Callable[[str, int, int, str], list[list]]) -> list[list]:
        key = (provider, symbol, interval)
        if key not in self._cache:
            self._cache[key] = fetcher(symbol, start_ms, end_ms, interval)
        return self._cache[key]


def _ms_to_dt(value: int | float | str) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000.0, tz=timezone.utc)


def parse_klines_observation(symbol: str, rows: list[list], *, provider: str, interval: str = "15m") -> PriceObservation:
    if not rows:
        raise ValueError("no_klines")
    highs = [float(r[2]) for r in rows]
    lows = [float(r[3]) for r in rows]
    observed = float(rows[-1][4])
    entry = float(rows[0][4])
    start = _ms_to_dt(rows[0][0])
    end = _ms_to_dt(rows[-1][6] if len(rows[-1]) > 6 else rows[-1][0])
    return PriceObservation(symbol=symbol, observed_price=observed, high_price=max(highs), low_price=min(lows), provider=provider, interval=interval, kline_count=len(rows), observation_start_ts=start, observation_end_ts=end, entry_price=entry)


def fetch_binance_klines_window(symbol: str, start_ts_ms: int, end_ts_ms: int, interval: str = "15m") -> list[list]:
    return fetch_json("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "startTime": start_ts_ms, "endTime": end_ts_ms, "limit": 1500})


def observe_binance_window(symbol: str, start_ts_ms: int, end_ts_ms: int, interval: str = "15m", budget: RequestBudget | None = None, cache: KlineCache | None = None) -> PriceObservation:
    if budget and not budget.consume("binance"):
        raise RuntimeError("request_budget_exhausted")
    binance_symbol = normalize_binance_symbol(symbol)
    fetcher = fetch_binance_klines_window
    rows = cache.get("binance", binance_symbol, interval, start_ts_ms, end_ts_ms, fetcher) if cache else fetcher(binance_symbol, start_ts_ms, end_ts_ms, interval)
    return parse_klines_observation(binance_symbol, rows, provider="binance", interval=interval)


def classify_price_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
        return "rate_limited"
    msg = str(exc).lower()
    if "429" in msg or "rate limit" in msg or "too many" in msg or "限流" in msg:
        return "rate_limited"
    if "no_klines" in msg:
        return "no_klines"
    if "invalid symbol" in msg or "symbol" in msg and "not" in msg:
        return "symbol_not_found"
    return "network_error"
