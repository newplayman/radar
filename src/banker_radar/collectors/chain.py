from __future__ import annotations

from collections.abc import Callable

from banker_radar.models import ChainSignalFeature
from banker_radar.utils.rate_limit import ProviderHealth

ProviderFn = Callable[[], list[ChainSignalFeature]]


def collect_chain_features(providers: list[ProviderFn], health: dict[str, ProviderHealth] | None = None) -> list[ChainSignalFeature]:
    """Try chain-data providers in order and return the first non-empty result.

    Provider failures are intentionally swallowed so free-tier/rate-limited chain
    enrichment degrades to market-only scans instead of breaking Telegram pushes.
    """
    for idx, provider in enumerate(providers):
        name = getattr(provider, "__name__", f"provider_{idx}")
        provider_health = health.get(name) if health else None
        if provider_health and not provider_health.available():
            continue
        try:
            features = provider()
            if provider_health:
                provider_health.record_success()
            if features:
                return features
        except Exception as exc:
            if provider_health:
                provider_health.record_failure(exc)
            continue
    return []
