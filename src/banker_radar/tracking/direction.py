from __future__ import annotations

from banker_radar.models import DirectionDecision

_LONG_KINDS = {"空头燃料", "暗流吸筹", "链上聪明钱", "链上链下共振"}
_SHORT_KINDS = {"空头压制"}
_VALID = {"long", "short", "neutral"}


def infer_signal_direction(kind: str, metadata: dict | None = None) -> DirectionDecision:
    metadata = metadata or {}
    override = metadata.get("direction") or metadata.get("signal_direction")
    if override in _VALID:
        return DirectionDecision(str(override), "metadata_override")
    if kind in _LONG_KINDS:
        return DirectionDecision("long", "kind_rule")
    if kind in _SHORT_KINDS:
        return DirectionDecision("short", "kind_rule")
    return DirectionDecision("neutral", "neutral_default")
