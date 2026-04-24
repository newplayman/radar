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


TRACKING_STATUSES = {"pending", "in_progress", "completed", "failed_retryable", "failed_permanent", "expired"}


@dataclass(frozen=True)
class DirectionDecision:
    direction: str
    source: str

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.direction == other
        return super().__eq__(other)


@dataclass(frozen=True)
class SignalTrackingRecord:
    signal_id: int
    symbol: str
    kind: str
    source: str
    direction: str
    signal_ts: datetime
    entry_price: float
    window_minutes: int
    due_ts: datetime
    id: int | None = None
    status: str = "pending"
    observed_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    return_pct: float | None = None
    max_runup_pct: float | None = None
    max_drawdown_pct: float | None = None
    success: bool | None = None
    error: str = ""
    retry_count: int = 0
    price_provider: str = ""
    provider_interval: str = ""
    metadata: dict = field(default_factory=dict)

    def is_due(self, now: datetime) -> bool:
        return self.status == "pending" and now >= self.due_ts


@dataclass(frozen=True)
class BacktestSummary:
    kind: str
    window_minutes: int
    total: int
    wins: int
    avg_return_pct: float
    directional_total: int | None = None
    avg_max_runup_pct: float = 0.0
    avg_max_drawdown_pct: float = 0.0
    min_samples: int = 5
    outlier_count: int = 0

    @property
    def win_rate_pct(self) -> float:
        denominator = self.directional_total if self.directional_total is not None else self.total
        return (self.wins / denominator * 100) if denominator else 0.0

    @property
    def sample_warning(self) -> str:
        return "样本不足" if self.total < self.min_samples else ""
