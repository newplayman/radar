from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass

from banker_radar.models import RadarSignal


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS radar_signals (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL,
  symbol TEXT NOT NULL,
  kind TEXT NOT NULL,
  score INTEGER NOT NULL,
  risk TEXT NOT NULL,
  reason TEXT NOT NULL,
  source TEXT NOT NULL,
  price_change_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
  oi_change_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
  funding_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_radar_signals_ts ON radar_signals (ts DESC);
CREATE INDEX IF NOT EXISTS idx_radar_signals_symbol_ts ON radar_signals (symbol, ts DESC);
CREATE INDEX IF NOT EXISTS idx_radar_signals_kind_ts ON radar_signals (kind, ts DESC);
CREATE INDEX IF NOT EXISTS idx_radar_signals_metadata_gin ON radar_signals USING GIN (metadata_json);
"""


@dataclass
class PostgresRadarStore:
    url: str
    psql_path: str = "psql"

    def _run(self, sql: str) -> str:
        env = dict(os.environ)
        env["PGCONNECT_TIMEOUT"] = env.get("PGCONNECT_TIMEOUT", "5")
        proc = subprocess.run([self.psql_path, self.url, "-v", "ON_ERROR_STOP=1", "-qAt"], input=sql, text=True, capture_output=True, timeout=20, env=env, check=False)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "psql failed")
        return proc.stdout

    def init(self) -> None:
        self._run(SCHEMA_SQL)

    def save_signal(self, signal: RadarSignal) -> None:
        s = signal.with_timestamp()
        payload = json.dumps(s.metadata or {}, ensure_ascii=False, sort_keys=True)
        sql = """
        INSERT INTO radar_signals(ts, symbol, kind, score, risk, reason, source, metadata_json)
        SELECT %(ts)s::timestamptz, %(symbol)s, %(kind)s, %(score)s::int, %(risk)s, %(reason)s, %(source)s, %(metadata)s::jsonb;
        """
        # psql stdin cannot safely bind params without psycopg, so use JSON recordset as one escaped literal.
        row = json.dumps({
            "ts": s.created_at,
            "symbol": s.symbol,
            "kind": s.kind,
            "score": s.score,
            "risk": s.risk,
            "reason": s.reason,
            "source": s.source,
            "metadata": payload,
        }, ensure_ascii=False)
        safe = row.replace("'", "''")
        self._run(
            """
            WITH r AS (SELECT * FROM jsonb_to_record('%s'::jsonb) AS x(ts text, symbol text, kind text, score int, risk text, reason text, source text, metadata text))
            INSERT INTO radar_signals(ts, symbol, kind, score, risk, reason, source, metadata_json)
            SELECT ts::timestamptz, symbol, kind, score, risk, reason, source, metadata::jsonb FROM r;
            """ % safe
        )

    def latest_signals(self, limit: int = 20) -> list[RadarSignal]:
        sql = f"""
        SELECT COALESCE(jsonb_agg(row_to_json(t)), '[]'::jsonb)::text
        FROM (
          SELECT ts AS created_at, symbol, kind, score, reason, risk, source, metadata_json
          FROM radar_signals ORDER BY ts DESC, id DESC LIMIT {int(limit)}
        ) t;
        """
        data = json.loads((self._run(sql).strip() or "[]"))
        return [
            RadarSignal(
                symbol=r["symbol"],
                kind=r["kind"],
                score=int(r["score"]),
                reason=r["reason"],
                risk=r["risk"],
                source=r["source"],
                created_at=r["created_at"],
                metadata=r.get("metadata_json") or {},
            )
            for r in data
        ]
