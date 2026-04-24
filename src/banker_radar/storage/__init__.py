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
    """Create the configured signal store.

    Runtime storage is PostgreSQL-first.  SQLite remains available only when it
    is explicitly requested with ``storage.backend: sqlite`` (mainly for unit
    tests and local throw-away smoke tests).  A postgres configuration must not
    silently fall back to SQLite, otherwise production can split data across two
    stores and make tracking/reviews inconsistent.
    """
    cfg = config or {}
    storage = cfg.get("storage", {}) if isinstance(cfg, dict) else {}
    backend = str(storage.get("backend") or "postgres").lower()

    if backend in {"postgres", "postgresql", "auto"}:
        from banker_radar.storage.postgres import PostgresRadarStore

        pg_cfg = storage.get("postgres", {}) or {}
        url_env = pg_cfg.get("url_env", "DATABASE_URL")
        url = os.getenv(url_env) or pg_cfg.get("url")
        if not url:
            raise RuntimeError(
                f"生产存储需要 PostgreSQL：请设置 {url_env}，或仅在测试中显式配置 storage.backend=sqlite。"
            )
        return PostgresRadarStore(url=url, psql_path=pg_cfg.get("psql_path", "psql"))

    if backend == "sqlite":
        sqlite_cfg = storage.get("sqlite", {}) or {}
        return RadarStore(db_path or sqlite_cfg.get("path", "data/radar.db"))

    raise RuntimeError(f"不支持的 storage.backend: {backend}")
