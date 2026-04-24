from __future__ import annotations


def _pct(new: float, old: float) -> float:
    return ((new - old) / old * 100.0) if old else 0.0


def calculate_performance(direction: str, *, entry: float, observed: float, high: float, low: float, success_threshold_pct: float, outlier_return_pct: float = 80.0) -> dict:
    if entry <= 0:
        raise ValueError("entry_price_must_be_positive")
    if direction == "short":
        ret = (entry - observed) / entry * 100.0
        runup = (entry - low) / entry * 100.0
        drawdown = (entry - high) / entry * 100.0
    else:
        ret = _pct(observed, entry)
        runup = _pct(high, entry)
        drawdown = _pct(low, entry)
    success = None if direction == "neutral" else ret >= success_threshold_pct
    is_outlier = any(abs(v) >= outlier_return_pct for v in (ret, runup, drawdown))
    return {"return_pct": ret, "max_runup_pct": runup, "max_drawdown_pct": drawdown, "success": success, "is_outlier": is_outlier}
