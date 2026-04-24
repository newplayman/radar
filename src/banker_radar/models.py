from __future__ import annotations

from dataclasses import dataclass, field
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
class TokenAuditResult:
    chain: str
    token_address: str
    risk_level: str = "UNKNOWN"
    risk_score: int = 0
    is_supported: bool = False
    has_result: bool = False
    buy_tax_pct: float | None = None
    sell_tax_pct: float | None = None
    raw: dict = field(default_factory=dict)

    @property
    def blocks_positive_signal(self) -> bool:
        return self.has_result and self.is_supported and (self.risk_level.upper() == "HIGH" or self.risk_score >= 4)


@dataclass(frozen=True)
class ChainSignalFeature:
    symbol: str
    chain: str
    provider: str
    token_address: str = ""
    direction: str = "buy"
    smart_wallet_count: int = 0
    whale_count: int = 0
    total_value_usd: float = 0.0
    exit_rate_pct: float = 0.0
    max_gain_pct: float = 0.0
    status: str = ""
    tags: list[str] = field(default_factory=list)
    heat_score: float = 0.0
    audit: TokenAuditResult | None = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RadarSignal:
    symbol: str
    kind: str
    score: int
    reason: str
    risk: str
    source: str
    created_at: str = ""
    metadata: dict = field(default_factory=dict)

    def with_timestamp(self) -> "RadarSignal":
        if self.created_at:
            return self
        return RadarSignal(
            symbol=self.symbol,
            kind=self.kind,
            score=self.score,
            reason=self.reason,
            risk=self.risk,
            source=self.source,
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=dict(self.metadata),
        )
