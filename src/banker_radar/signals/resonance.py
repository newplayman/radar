from __future__ import annotations

from banker_radar.models import RadarSignal


def _clamp_int(v: float) -> int:
    return int(max(0, min(100, round(v))))


def build_resonance_signals(contract_signals: list[RadarSignal], chain_signals: list[RadarSignal], *, min_score: int = 75) -> list[RadarSignal]:
    contracts_by_symbol: dict[str, list[RadarSignal]] = {}
    for s in contract_signals:
        contracts_by_symbol.setdefault(s.symbol.upper(), []).append(s)

    out: list[RadarSignal] = []
    for chain in chain_signals:
        matches = contracts_by_symbol.get(chain.symbol.upper(), [])
        if not matches:
            continue
        best_contract = max(matches, key=lambda s: s.score)
        score = _clamp_int(max(best_contract.score, chain.score) + 8 + min((best_contract.score + chain.score) / 20, 10))
        if score < min_score:
            continue
        risk = "中高" if score >= 85 or best_contract.risk in {"高", "中高"} else "中"
        reason = f"聪明钱信号 + 合约异动共振：链上({chain.reason})；合约({best_contract.reason})"
        metadata = dict(chain.metadata)
        metadata.update({
            "chain_signal_score": chain.score,
            "contract_signal_score": best_contract.score,
            "contract_kind": best_contract.kind,
            "contract_source": best_contract.source,
        })
        out.append(
            RadarSignal(
                symbol=chain.symbol,
                kind="链上链下共振",
                score=score,
                reason=reason,
                risk=risk,
                source=f"{chain.source}+{best_contract.source}",
                metadata=metadata,
            )
        )
    out.sort(key=lambda s: s.score, reverse=True)
    return out
