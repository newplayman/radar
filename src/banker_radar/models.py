from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Candle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume_usd: float


@dataclass(frozen=True)
class AccumulationResult:
    symbol: str
    in_pool: bool
    sideways_days: int
    range_pct: float
    avg_volume_usd: float
    slope_pct: float
    score: int


@dataclass(frozen=True)
class MarketFeature:
    symbol: str
    price_change_pct: float
    oi_delta_pct: float
    funding_rate_pct: float
    volume_usd_24h: float
    oi_usd: float
    source: str = ""


@dataclass(frozen=True)
class RadarSignal:
    symbol: str
    kind: str
    score: int
    reason: str
    risk: str
    source: str
    created_at: str = ""

    def with_timestamp(self) -> "RadarSignal":
        if self.created_at:
            return self
        return RadarSignal(
            symbol=self.symbol, kind=self.kind, score=self.score, reason=self.reason,
            risk=self.risk, source=self.source, created_at=datetime.now(timezone.utc).isoformat()
        )
