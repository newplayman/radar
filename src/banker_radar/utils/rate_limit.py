from __future__ import annotations

import time
from dataclasses import dataclass


RATE_LIMIT_MARKERS = ("429", "rate limit", "too many requests", "limit exceeded", "限流")


def is_rate_limited_error(error: BaseException | str) -> bool:
    text = str(error).lower()
    return any(marker in text for marker in RATE_LIMIT_MARKERS)


@dataclass
class ProviderHealth:
    max_failures: int = 3
    cooldown_seconds: int = 300
    failures: int = 0
    cooldown_until: float = 0.0
    last_error: str = ""

    def available(self, *, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return now >= self.cooldown_until

    def record_success(self) -> None:
        self.failures = 0
        self.cooldown_until = 0.0
        self.last_error = ""

    def record_failure(self, error: BaseException | str, *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self.failures += 1
        self.last_error = str(error)
        if self.failures >= self.max_failures or is_rate_limited_error(error):
            # Exponential backoff capped at 1 hour; keeps free/subscribed accounts self-healing.
            multiplier = min(12, max(1, self.failures - self.max_failures + 1))
            self.cooldown_until = now + self.cooldown_seconds * multiplier
