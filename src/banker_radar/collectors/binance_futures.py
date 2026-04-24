from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Iterable

from banker_radar.models import Candle, MarketFeature

BASE = "https://fapi.binance.com"


def fetch_json(path: str, params: dict | None = None):
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(BASE + path + query, headers={"User-Agent": "banker-radar/0.1"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_binance_candles(raw: list[list]) -> list[Candle]:
    return [
        Candle(ts=int(r[0]), open=float(r[1]), high=float(r[2]), low=float(r[3]), close=float(r[4]), volume_usd=float(r[7]))
        for r in raw
    ]


def fetch_klines(symbol: str, interval: str = "1d", limit: int = 60) -> list[Candle]:
    return parse_binance_candles(fetch_json("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit}))


def fetch_top_usdt_symbols(limit: int = 40) -> list[str]:
    rows = fetch_json("/fapi/v1/ticker/24hr")
    usdt = [r for r in rows if r.get("symbol", "").endswith("USDT") and float(r.get("quoteVolume", 0) or 0) > 0]
    usdt.sort(key=lambda r: float(r.get("quoteVolume", 0) or 0), reverse=True)
    return [r["symbol"] for r in usdt[:limit]]


def _funding_pct(rate: str | float | int) -> float:
    return float(rate) * 100


def merge_binance_features(tickers: list[dict], oi_rows: list[dict], funding_rows: list[dict]) -> list[MarketFeature]:
    ticker_by_symbol = {r["symbol"]: r for r in tickers if "symbol" in r}
    funding_by_symbol = {r["symbol"]: r for r in funding_rows if "symbol" in r}
    out: list[MarketFeature] = []
    for oi in oi_rows:
        symbol = oi.get("symbol")
        if not symbol or symbol not in ticker_by_symbol:
            continue
        ticker = ticker_by_symbol[symbol]
        funding = funding_by_symbol.get(symbol, {})
        out.append(MarketFeature(
            symbol=symbol,
            price_change_pct=float(ticker.get("priceChangePercent", 0) or 0),
            oi_delta_pct=float(oi.get("sumOpenInterestValueDeltaPct", 0) or 0),
            funding_rate_pct=_funding_pct(funding.get("lastFundingRate", 0) or 0),
            volume_usd_24h=float(ticker.get("quoteVolume", 0) or 0),
            oi_usd=float(oi.get("sumOpenInterestValue", 0) or 0),
            source="binance",
        ))
    return out


def fetch_oi_delta(symbol: str, period: str = "1h", limit: int = 2) -> dict:
    rows = fetch_json("/futures/data/openInterestHist", {"symbol": symbol, "period": period, "limit": limit})
    if not rows:
        return {"symbol": symbol, "sumOpenInterestValue": "0", "sumOpenInterestValueDeltaPct": "0"}
    latest = rows[-1]
    prev = rows[-2] if len(rows) > 1 else latest
    latest_val = float(latest.get("sumOpenInterestValue", 0) or 0)
    prev_val = float(prev.get("sumOpenInterestValue", 0) or 0)
    delta_pct = ((latest_val - prev_val) / prev_val * 100) if prev_val else 0.0
    return {"symbol": symbol, "sumOpenInterestValue": str(latest_val), "sumOpenInterestValueDeltaPct": str(delta_pct)}


def fetch_features(symbols: Iterable[str]) -> list[MarketFeature]:
    symbols = list(symbols)
    all_tickers = fetch_json("/fapi/v1/ticker/24hr")
    tickers = [r for r in all_tickers if r.get("symbol") in symbols]
    funding = [fetch_json("/fapi/v1/premiumIndex", {"symbol": s}) for s in symbols]
    oi_rows = [fetch_oi_delta(s) for s in symbols]
    return merge_binance_features(tickers, oi_rows, funding)
