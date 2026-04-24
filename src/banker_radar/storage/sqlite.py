from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from banker_radar.models import RadarSignal


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
