from __future__ import annotations

from banker_radar.models import AccumulationResult, MarketFeature, RadarSignal


def _clamp_int(v: float) -> int:
    return int(max(0, min(100, round(v))))


def score_market(feature: MarketFeature, accumulation: AccumulationResult | None = None) -> RadarSignal:
    in_pool = bool(accumulation and accumulation.in_pool)
    acc_score = accumulation.score if accumulation else 0

    # 🎯 暗流吸筹：横盘池内，OI 涨，价格没怎么动
    if in_pool and feature.oi_delta_pct >= 3 and abs(feature.price_change_pct) <= 3:
        score = _clamp_int(45 + acc_score * 0.25 + min(feature.oi_delta_pct * 4, 20) + min(feature.volume_usd_24h / 2_000_000, 10))
        reason = f"横盘{accumulation.sideways_days}天，OI {feature.oi_delta_pct:+.2f}%，价格 {feature.price_change_pct:+.2f}%"
        return RadarSignal(feature.symbol, "暗流吸筹", score, reason, "中", feature.source or "market")

    # 🔥 空头燃料：价格涨但资金费率仍为负，可能有轧空燃料
    if feature.price_change_pct >= 3 and feature.funding_rate_pct < 0 and feature.volume_usd_24h >= 1_000_000:
        funding_bonus = min(abs(feature.funding_rate_pct) * 400, 25)
        score = _clamp_int(42 + min(feature.price_change_pct * 2, 20) + funding_bonus + min(max(feature.oi_delta_pct, 0) * 2, 10))
        risk = "高" if feature.price_change_pct >= 8 or feature.funding_rate_pct <= -0.05 else "中高"
        reason = f"价格 {feature.price_change_pct:+.2f}%，费率 {feature.funding_rate_pct:+.4f}%，OI {feature.oi_delta_pct:+.2f}%"
        return RadarSignal(feature.symbol, "空头燃料", score, reason, risk, feature.source or "market")

    # 📊 综合异动：兜底，避免漏掉明显 OI/成交量变化
    score = _clamp_int((acc_score * 0.25) + min(abs(feature.oi_delta_pct) * 5, 35) + min(abs(feature.price_change_pct) * 2, 20) + min(feature.volume_usd_24h / 2_000_000, 20))
    kind = "综合异动" if score >= 40 else "轻微异动"
    risk = "高" if abs(feature.price_change_pct) >= 10 else "中" if score >= 60 else "低"
    reason = f"OI {feature.oi_delta_pct:+.2f}%，价格 {feature.price_change_pct:+.2f}%，费率 {feature.funding_rate_pct:+.4f}%"
    return RadarSignal(feature.symbol, kind, score, reason, risk, feature.source or "market")
