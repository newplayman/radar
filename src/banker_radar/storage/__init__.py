from __future__ import annotations

import os
from datetime import datetime
from typing import Protocol

from banker_radar.models import BacktestSummary, RadarSignal, SignalTrackingRecord
from banker_radar.storage.sqlite import RadarStore


class SignalStore(Protocol):
    def init(self) -> None: ...
    def save_signal(self, signal: RadarSignal) -> None: ...
    def latest_signals(self, limit: int = 20) -> list[RadarSignal]: ...
    def enqueue_tracking(self, windows_minutes: list[int], *, since: datetime | None = None, limit: int = 500) -> int: ...
    def due_tracking_records(self, *, now: datetime, limit: int = 50, max_age_hours: int = 72) -> list[SignalTrackingRecord]: ...
    def backtest_summaries(self, *, period_start: datetime, period_end: datetime, min_samples: int = 5) -> list[BacktestSummary]: ...
    def record_review_send(self, period_start: datetime, period_end: datetime, channel: str, content_hash: str, *, force: bool = False, metadata: dict | None = None) -> bool: ...


def create_store(config: dict | None = None, *, db_path: str | None = None) -> SignalStore:
    cfg = config or {}
    storage = cfg.get("storage", {}) if isinstance(cfg, dict) else {}
    backend = str(storage.get("backend") or "sqlite").lower()
    if backend == "postgres":
        from banker_radar.storage.postgres import PostgresRadarStore

        pg_cfg = storage.get("postgres", {}) or {}
        url_env = pg_cfg.get("url_env", "DATABASE_URL")
        url = os.getenv(url_env) or pg_cfg.get("url")
        if not url:
            if db_path:
                return RadarStore(db_path)
            raise RuntimeError(f"storage.backend=postgres 但未设置 {url_env}")
        return PostgresRadarStore(url=url, psql_path=pg_cfg.get("psql_path", "psql"))

    sqlite_cfg = storage.get("sqlite", {}) or {}
    return RadarStore(db_path or sqlite_cfg.get("path", "data/radar.db"))
