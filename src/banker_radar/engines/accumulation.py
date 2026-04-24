from __future__ import annotations

from banker_radar.models import AccumulationResult, Candle


def _clamp(v: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, v))


def analyze_accumulation(
    symbol: str,
    candles: list[Candle],
    *,
    min_sideways_days: int = 45,
    max_range_pct: float = 80,
    max_avg_vol_usd: float = 20_000_000,
    max_abs_slope_pct: float = 12,
) -> AccumulationResult:
    if not candles:
        return AccumulationResult(symbol, False, 0, 0.0, 0.0, 0.0, 0)

    window = candles[-max(min_sideways_days, min(len(candles), 120)):] if len(candles) >= min_sideways_days else candles
    highs = [c.high for c in window]
    lows = [c.low for c in window]
    closes = [c.close for c in window]
    vols = [c.volume_usd for c in window]
    low = min(lows)
    high = max(highs)
    mid = (high + low) / 2 if high + low else max(closes[-1], 1e-9)
    range_pct = ((high - low) / mid) * 100 if mid else 0.0
    avg_volume = sum(vols) / len(vols)
    first = closes[0] or 1e-9
    slope_pct = ((closes[-1] - first) / first) * 100

    days_score = _clamp((len(candles) / min_sideways_days) * 25)
    range_score = _clamp((1 - range_pct / max_range_pct) * 35)
    vol_score = _clamp((1 - avg_volume / max_avg_vol_usd) * 25)
    slope_score = _clamp((1 - abs(slope_pct) / max_abs_slope_pct) * 15)
    score = int(round(days_score + range_score + vol_score + slope_score))

    in_pool = (
        len(candles) >= min_sideways_days
        and range_pct <= max_range_pct
        and avg_volume <= max_avg_vol_usd
        and abs(slope_pct) <= max_abs_slope_pct
        and score >= 70
    )
    return AccumulationResult(symbol, in_pool, len(candles), round(range_pct, 4), round(avg_volume, 2), round(slope_pct, 4), score)
