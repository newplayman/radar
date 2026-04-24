from __future__ import annotations

from banker_radar.models import ChainSignalFeature, RadarSignal


def _clamp_int(v: float) -> int:
    return int(max(0, min(100, round(v))))


def _risk_for(feature: ChainSignalFeature, score: int) -> str:
    if feature.exit_rate_pct >= 50 or feature.max_gain_pct >= 120:
        return "高"
    if score >= 80 or feature.whale_count > 0:
        return "中高"
    return "中"


def score_chain_feature(
    feature: ChainSignalFeature,
    *,
    min_score: int = 60,
    min_smart_wallets: int = 2,
    max_exit_rate_pct: float = 50,
    max_gain_pct_for_fresh_signal: float = 80,
) -> RadarSignal | None:
    """Convert provider-neutral smart-money data into a cautious radar signal.

    High-risk token audits block positive signals. Freshness/rate-limit concerns are
    handled at collector level; this scorer focuses on quality and risk.
    """
    if feature.audit and feature.audit.blocks_positive_signal:
        return None
    if feature.direction and feature.direction.lower() not in {"buy", "long", "in"}:
        return None
    if feature.smart_wallet_count < min_smart_wallets:
        return None
    if feature.exit_rate_pct > max_exit_rate_pct:
        return None

    score = 45
    score += min(feature.smart_wallet_count * 6, 30)
    score += min(feature.whale_count * 8, 16)
    score += min(feature.total_value_usd / 10_000, 10)
    score += 8 if feature.status.lower() == "active" else 0
    score += 6 if any("whale" in t.lower() for t in feature.tags) else 0
    if 0 < feature.max_gain_pct <= max_gain_pct_for_fresh_signal:
        score += 5
    elif feature.max_gain_pct > max_gain_pct_for_fresh_signal:
        score -= min((feature.max_gain_pct - max_gain_pct_for_fresh_signal) / 4, 15)
    score -= min(feature.exit_rate_pct / 5, 12)
    score += min(feature.heat_score / 10, 8)
    score = _clamp_int(score)
    if score < min_score:
        return None

    reason_parts = [f"{feature.smart_wallet_count} 个聪明钱地址买入"]
    if feature.whale_count:
        reason_parts.append(f"鲸鱼标签 {feature.whale_count} 个")
    if feature.exit_rate_pct:
        reason_parts.append(f"退出率 {feature.exit_rate_pct:.1f}%")
    if feature.max_gain_pct:
        reason_parts.append(f"最高涨幅 {feature.max_gain_pct:.1f}%")
    if feature.tags:
        reason_parts.append("标签:" + ",".join(feature.tags[:3]))

    return RadarSignal(
        symbol=feature.symbol,
        kind="链上聪明钱",
        score=score,
        reason="；".join(reason_parts),
        risk=_risk_for(feature, score),
        source=feature.provider,
        metadata={
            "chain": feature.chain,
            "provider": feature.provider,
            "token_address": feature.token_address,
            "smart_wallet_count": feature.smart_wallet_count,
            "whale_count": feature.whale_count,
            "exit_rate_pct": feature.exit_rate_pct,
            "max_gain_pct": feature.max_gain_pct,
            "tags": feature.tags,
            "audit": feature.audit.raw if feature.audit else None,
        },
    )


def score_chain_features(features: list[ChainSignalFeature], **kwargs) -> list[RadarSignal]:
    signals = [score_chain_feature(f, **kwargs) for f in features]
    return [s for s in signals if s is not None]
