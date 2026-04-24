from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from banker_radar.models import BacktestSummary, RadarSignal, SignalTrackingRecord
from banker_radar.tracking.direction import infer_signal_direction


def _dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _iso(value: datetime) -> str:
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


class RadarStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path)

    def init(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    source TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            cols = [r[1] for r in db.execute("PRAGMA table_info(signals)").fetchall()]
            if "metadata_json" not in cols:
                db.execute("ALTER TABLE signals ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
            db.execute("CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at DESC)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol_created ON signals(symbol, created_at DESC)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_signals_kind_created ON signals(kind, created_at DESC)")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    source TEXT NOT NULL,
                    direction TEXT NOT NULL DEFAULT 'neutral',
                    signal_ts TEXT NOT NULL,
                    entry_price REAL NOT NULL DEFAULT 0,
                    window_minutes INTEGER NOT NULL,
                    due_ts TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    observed_price REAL,
                    high_price REAL,
                    low_price REAL,
                    return_pct REAL,
                    max_runup_pct REAL,
                    max_drawdown_pct REAL,
                    success INTEGER,
                    error TEXT NOT NULL DEFAULT '',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    locked_at TEXT,
                    completed_at TEXT,
                    expired_at TEXT,
                    observation_start_ts TEXT,
                    observation_end_ts TEXT,
                    price_provider TEXT NOT NULL DEFAULT '',
                    provider_interval TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(signal_id, window_minutes),
                    CHECK (status IN ('pending', 'in_progress', 'completed', 'failed_retryable', 'failed_permanent', 'expired')),
                    CHECK (window_minutes > 0),
                    CHECK (entry_price >= 0)
                )
                """
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_signal_tracking_due ON signal_tracking(status, due_ts)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_signal_tracking_symbol_ts ON signal_tracking(symbol, signal_ts DESC)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_signal_tracking_kind_ts ON signal_tracking(kind, signal_ts DESC)")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_cooldowns (
                    provider TEXT PRIMARY KEY,
                    blocked_until TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS review_sends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(period_start, period_end, channel)
                )
                """
            )

    def save_signal(self, signal: RadarSignal) -> None:
        s = signal.with_timestamp()
        with self._connect() as db:
            db.execute(
                "INSERT INTO signals(created_at, symbol, kind, score, reason, risk, source, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (s.created_at, s.symbol, s.kind, s.score, s.reason, s.risk, s.source, json.dumps(s.metadata or {}, ensure_ascii=False, sort_keys=True)),
            )

    def latest_signals(self, limit: int = 20) -> list[RadarSignal]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT created_at, symbol, kind, score, reason, risk, source, metadata_json FROM signals ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out: list[RadarSignal] = []
        for r in rows:
            try:
                metadata = json.loads(r[7] or "{}")
            except json.JSONDecodeError:
                metadata = {}
            out.append(RadarSignal(symbol=r[1], kind=r[2], score=r[3], reason=r[4], risk=r[5], source=r[6], created_at=r[0], metadata=metadata))
        return out

    def enqueue_tracking(self, windows_minutes: list[int], *, since: datetime | None = None, limit: int = 500) -> int:
        since = since or (datetime.now(timezone.utc) - timedelta(days=2))
        inserted = 0
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, created_at, symbol, kind, score, risk, source, metadata_json FROM signals WHERE datetime(created_at) >= datetime(?) ORDER BY created_at DESC, id DESC LIMIT ?",
                (_iso(since), int(limit)),
            ).fetchall()
            for signal_id, created_at, symbol, kind, score, risk, source, metadata_json in rows:
                try:
                    metadata = json.loads(metadata_json or "{}")
                except json.JSONDecodeError:
                    metadata = {}
                decision = infer_signal_direction(kind, metadata)
                signal_ts = _dt(created_at)
                entry = float(metadata.get("entry_price") or metadata.get("price") or metadata.get("last_price") or 0)
                tracking_meta = dict(metadata)
                tracking_meta.update({"risk": risk, "score": int(score), "direction_source": decision.source, "original_source": source})
                for w in windows_minutes:
                    cur = db.execute(
                        """
                        INSERT OR IGNORE INTO signal_tracking(signal_id, symbol, kind, source, direction, signal_ts, entry_price, window_minutes, due_ts, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (signal_id, symbol, kind, source, decision.direction, _iso(signal_ts), entry, int(w), _iso(signal_ts + timedelta(minutes=int(w))), json.dumps(tracking_meta, ensure_ascii=False, sort_keys=True)),
                    )
                    inserted += cur.rowcount
        return inserted

    def _row_to_tracking(self, r) -> SignalTrackingRecord:
        try:
            metadata = json.loads(r[27] or "{}")
        except Exception:
            metadata = {}
        return SignalTrackingRecord(
            id=r[0], signal_id=r[1], symbol=r[2], kind=r[3], source=r[4], direction=r[5], signal_ts=_dt(r[6]), entry_price=float(r[7] or 0), window_minutes=int(r[8]), due_ts=_dt(r[9]), status=r[10], observed_price=r[11], high_price=r[12], low_price=r[13], return_pct=r[14], max_runup_pct=r[15], max_drawdown_pct=r[16], success=(None if r[17] is None else bool(r[17])), error=r[18] or "", retry_count=int(r[19] or 0), price_provider=r[25] or "", provider_interval=r[26] or "", metadata=metadata,
        )

    def due_tracking_records(self, *, now: datetime, limit: int = 50, max_age_hours: int = 72) -> list[SignalTrackingRecord]:
        now_iso = _iso(now)
        expire_before = _iso(now - timedelta(hours=max_age_hours))
        with self._connect() as db:
            db.execute("UPDATE signal_tracking SET status='expired', expired_at=?, updated_at=? WHERE status IN ('pending','failed_retryable') AND datetime(signal_ts) < datetime(?)", (now_iso, now_iso, expire_before))
            rows = db.execute("SELECT * FROM signal_tracking WHERE status IN ('pending','failed_retryable') AND datetime(due_ts) <= datetime(?) ORDER BY due_ts ASC, id ASC LIMIT ?", (now_iso, int(limit))).fetchall()
            ids = [r[0] for r in rows]
            if ids:
                db.executemany("UPDATE signal_tracking SET status='in_progress', locked_at=?, updated_at=? WHERE id=?", [(now_iso, now_iso, i) for i in ids])
        return [self._row_to_tracking(r) for r in rows]

    def complete_tracking(self, record: SignalTrackingRecord, *, observed_price: float, high_price: float, low_price: float, return_pct: float, max_runup_pct: float, max_drawdown_pct: float, success: bool | None, metadata: dict | None = None, observation_start_ts: datetime | None = None, observation_end_ts: datetime | None = None, price_provider: str = "", provider_interval: str = "") -> None:
        merged = dict(record.metadata)
        if metadata:
            merged.update(metadata)
        with self._connect() as db:
            db.execute(
                """
                UPDATE signal_tracking SET status='completed', observed_price=?, high_price=?, low_price=?, return_pct=?, max_runup_pct=?, max_drawdown_pct=?, success=?, completed_at=?, updated_at=?, observation_start_ts=?, observation_end_ts=?, price_provider=?, provider_interval=?, metadata_json=? WHERE id=?
                """,
                (observed_price, high_price, low_price, return_pct, max_runup_pct, max_drawdown_pct, None if success is None else int(success), _iso(datetime.now(timezone.utc)), _iso(datetime.now(timezone.utc)), _iso(observation_start_ts) if observation_start_ts else None, _iso(observation_end_ts) if observation_end_ts else None, price_provider or merged.get("price_provider", ""), provider_interval or merged.get("interval", ""), json.dumps(merged, ensure_ascii=False, sort_keys=True), record.id),
            )

    def fail_tracking(self, record: SignalTrackingRecord, *, status: str, error: str, retry_count: int | None = None) -> None:
        with self._connect() as db:
            db.execute("UPDATE signal_tracking SET status=?, error=?, retry_count=?, updated_at=? WHERE id=?", (status, error, record.retry_count + 1 if retry_count is None else retry_count, _iso(datetime.now(timezone.utc)), record.id))

    def backtest_summaries(self, *, period_start: datetime, period_end: datetime, min_samples: int = 5) -> list[BacktestSummary]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT kind, window_minutes, COUNT(*),
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END),
                       SUM(CASE WHEN success IS NOT NULL THEN 1 ELSE 0 END),
                       AVG(COALESCE(return_pct,0)), AVG(COALESCE(max_runup_pct,0)), AVG(COALESCE(max_drawdown_pct,0)),
                       SUM(CASE WHEN json_extract(metadata_json, '$.is_outlier') = 1 THEN 1 ELSE 0 END)
                FROM signal_tracking
                WHERE status='completed' AND datetime(signal_ts) >= datetime(?) AND datetime(signal_ts) < datetime(?)
                GROUP BY kind, window_minutes
                ORDER BY window_minutes ASC, COUNT(*) DESC, AVG(COALESCE(return_pct,0)) DESC
                """,
                (_iso(period_start), _iso(period_end)),
            ).fetchall()
        return [BacktestSummary(kind=r[0], window_minutes=int(r[1]), total=int(r[2]), wins=int(r[3] or 0), directional_total=int(r[4] or 0), avg_return_pct=float(r[5] or 0), avg_max_runup_pct=float(r[6] or 0), avg_max_drawdown_pct=float(r[7] or 0), min_samples=min_samples, outlier_count=int(r[8] or 0)) for r in rows]

    def set_provider_cooldown(self, provider: str, blocked_until: datetime, *, reason: str = "", retry_count: int = 1) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO provider_cooldowns(provider, blocked_until, reason, retry_count, updated_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(provider) DO UPDATE SET blocked_until=excluded.blocked_until, reason=excluded.reason, retry_count=excluded.retry_count, updated_at=excluded.updated_at",
                (provider, _iso(blocked_until), reason, retry_count, _iso(datetime.now(timezone.utc))),
            )

    def is_provider_blocked(self, provider: str, now: datetime) -> bool:
        with self._connect() as db:
            row = db.execute("SELECT blocked_until FROM provider_cooldowns WHERE provider=?", (provider,)).fetchone()
        return bool(row and _dt(row[0]) > now)

    def record_review_send(self, period_start: datetime, period_end: datetime, channel: str, content_hash: str, *, force: bool = False, metadata: dict | None = None) -> bool:
        with self._connect() as db:
            if force:
                db.execute("DELETE FROM review_sends WHERE period_start=? AND period_end=? AND channel=?", (_iso(period_start), _iso(period_end), channel))
            cur = db.execute(
                "INSERT OR IGNORE INTO review_sends(period_start, period_end, channel, content_hash, metadata_json) VALUES (?, ?, ?, ?, ?)",
                (_iso(period_start), _iso(period_end), channel, content_hash, json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)),
            )
            return cur.rowcount > 0
