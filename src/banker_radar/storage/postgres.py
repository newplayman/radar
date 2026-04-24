from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from banker_radar.models import BacktestSummary, RadarSignal, SignalTrackingRecord
from banker_radar.tracking.direction import infer_signal_direction


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
CREATE TABLE IF NOT EXISTS signal_tracking (
  id BIGSERIAL PRIMARY KEY,
  signal_id BIGINT NOT NULL REFERENCES radar_signals(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  kind TEXT NOT NULL,
  source TEXT NOT NULL,
  direction TEXT NOT NULL DEFAULT 'neutral',
  signal_ts TIMESTAMPTZ NOT NULL,
  entry_price DOUBLE PRECISION NOT NULL DEFAULT 0,
  window_minutes INTEGER NOT NULL,
  due_ts TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','failed_retryable','failed_permanent','expired')),
  observed_price DOUBLE PRECISION,
  high_price DOUBLE PRECISION,
  low_price DOUBLE PRECISION,
  return_pct DOUBLE PRECISION,
  max_runup_pct DOUBLE PRECISION,
  max_drawdown_pct DOUBLE PRECISION,
  success BOOLEAN,
  error TEXT NOT NULL DEFAULT '',
  retry_count INTEGER NOT NULL DEFAULT 0,
  locked_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  expired_at TIMESTAMPTZ,
  observation_start_ts TIMESTAMPTZ,
  observation_end_ts TIMESTAMPTZ,
  price_provider TEXT NOT NULL DEFAULT '',
  provider_interval TEXT NOT NULL DEFAULT '',
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(signal_id, window_minutes)
);
CREATE INDEX IF NOT EXISTS idx_signal_tracking_due ON signal_tracking (status, due_ts);
CREATE INDEX IF NOT EXISTS idx_signal_tracking_kind_ts ON signal_tracking (kind, signal_ts DESC);
CREATE TABLE IF NOT EXISTS provider_cooldowns (
  provider TEXT PRIMARY KEY,
  blocked_until TIMESTAMPTZ NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  retry_count INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS review_sends (
  id BIGSERIAL PRIMARY KEY,
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ NOT NULL,
  channel TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(period_start, period_end, channel)
);
"""




def _iso(value: datetime) -> str:
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


def _dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

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

    def enqueue_tracking(self, windows_minutes: list[int], *, since: datetime | None = None, limit: int = 500) -> int:
        since = since or (datetime.now(timezone.utc) - timedelta(days=2))
        inserted = 0
        # Fetch candidates client-side to preserve same direction inference as SQLite.
        safe_since = _iso(since).replace("'", "''")
        data = json.loads((self._run(f"""
        SELECT COALESCE(jsonb_agg(row_to_json(t)), '[]'::jsonb)::text FROM (
          SELECT id, ts AS created_at, symbol, kind, score, risk, source, metadata_json
          FROM radar_signals WHERE ts >= '{safe_since}'::timestamptz ORDER BY ts DESC, id DESC LIMIT {int(limit)}
        ) t;
        """).strip() or "[]"))
        rows = []
        for r in data:
            metadata = r.get("metadata_json") or {}
            decision = infer_signal_direction(r["kind"], metadata)
            signal_ts = _dt(r["created_at"])
            entry = float(metadata.get("entry_price") or metadata.get("price") or metadata.get("last_price") or 0)
            tracking_meta = dict(metadata)
            tracking_meta.update({"risk": r["risk"], "score": int(r["score"]), "direction_source": decision.source, "original_source": r["source"]})
            for w in windows_minutes:
                rows.append({"signal_id": r["id"], "symbol": r["symbol"], "kind": r["kind"], "source": r["source"], "direction": decision.direction, "signal_ts": _iso(signal_ts), "entry_price": entry, "window_minutes": int(w), "due_ts": _iso(signal_ts + timedelta(minutes=int(w))), "metadata_json": tracking_meta})
        for row in rows:
            safe = json.dumps(row, ensure_ascii=False).replace("'", "''")
            out = self._run(f"""
            WITH r AS (SELECT * FROM jsonb_to_record('{safe}'::jsonb) AS x(signal_id bigint, symbol text, kind text, source text, direction text, signal_ts text, entry_price float8, window_minutes int, due_ts text, metadata_json jsonb)),
            ins AS (
              INSERT INTO signal_tracking(signal_id, symbol, kind, source, direction, signal_ts, entry_price, window_minutes, due_ts, metadata_json)
              SELECT signal_id, symbol, kind, source, direction, signal_ts::timestamptz, entry_price, window_minutes, due_ts::timestamptz, metadata_json FROM r
              ON CONFLICT(signal_id, window_minutes) DO NOTHING RETURNING 1
            ) SELECT count(*) FROM ins;
            """).strip()
            inserted += int(out or 0)
        return inserted

    def due_tracking_records(self, *, now: datetime, limit: int = 50, max_age_hours: int = 72) -> list[SignalTrackingRecord]:
        now_s = _iso(now).replace("'", "''")
        expire_s = _iso(now - timedelta(hours=max_age_hours)).replace("'", "''")
        data = json.loads((self._run(f"""
        UPDATE signal_tracking SET status='expired', expired_at='{now_s}'::timestamptz, updated_at=now()
        WHERE status IN ('pending','failed_retryable') AND signal_ts < '{expire_s}'::timestamptz;
        WITH picked AS (
          SELECT id FROM signal_tracking
          WHERE status IN ('pending','failed_retryable') AND due_ts <= '{now_s}'::timestamptz
          ORDER BY due_ts ASC, id ASC LIMIT {int(limit)} FOR UPDATE SKIP LOCKED
        ), upd AS (
          UPDATE signal_tracking st SET status='in_progress', locked_at='{now_s}'::timestamptz, updated_at=now()
          FROM picked WHERE st.id=picked.id RETURNING st.*
        ) SELECT COALESCE(jsonb_agg(row_to_json(upd)), '[]'::jsonb)::text FROM upd;
        """).strip() or "[]"))
        return [SignalTrackingRecord(id=r["id"], signal_id=r["signal_id"], symbol=r["symbol"], kind=r["kind"], source=r["source"], direction=r["direction"], signal_ts=_dt(r["signal_ts"]), entry_price=float(r.get("entry_price") or 0), window_minutes=int(r["window_minutes"]), due_ts=_dt(r["due_ts"]), status=r["status"], observed_price=r.get("observed_price"), high_price=r.get("high_price"), low_price=r.get("low_price"), return_pct=r.get("return_pct"), max_runup_pct=r.get("max_runup_pct"), max_drawdown_pct=r.get("max_drawdown_pct"), success=r.get("success"), error=r.get("error") or "", retry_count=int(r.get("retry_count") or 0), price_provider=r.get("price_provider") or "", provider_interval=r.get("provider_interval") or "", metadata=r.get("metadata_json") or {}) for r in data]

    def complete_tracking(self, record: SignalTrackingRecord, **kwargs) -> None:
        merged = dict(record.metadata); merged.update(kwargs.get("metadata") or {})
        row = {
            "id": record.id,
            "observed_price": kwargs["observed_price"],
            "high_price": kwargs["high_price"],
            "low_price": kwargs["low_price"],
            "return_pct": kwargs["return_pct"],
            "max_runup_pct": kwargs["max_runup_pct"],
            "max_drawdown_pct": kwargs["max_drawdown_pct"],
            "success": kwargs.get("success"),
            "observation_start_ts": _iso(kwargs["observation_start_ts"]) if kwargs.get("observation_start_ts") else None,
            "observation_end_ts": _iso(kwargs["observation_end_ts"]) if kwargs.get("observation_end_ts") else None,
            "price_provider": kwargs.get("price_provider", ""),
            "provider_interval": kwargs.get("provider_interval", ""),
            "metadata_json": merged,
        }
        safe = json.dumps(row, ensure_ascii=False).replace("'", "''")
        self._run(f"""WITH r AS (SELECT * FROM jsonb_to_record('{safe}'::jsonb) AS x(id bigint, observed_price float8, high_price float8, low_price float8, return_pct float8, max_runup_pct float8, max_drawdown_pct float8, success boolean, observation_start_ts text, observation_end_ts text, price_provider text, provider_interval text, metadata_json jsonb))
        UPDATE signal_tracking st SET status='completed', observed_price=r.observed_price, high_price=r.high_price, low_price=r.low_price, return_pct=r.return_pct, max_runup_pct=r.max_runup_pct, max_drawdown_pct=r.max_drawdown_pct, success=r.success, completed_at=now(), updated_at=now(), observation_start_ts=NULLIF(r.observation_start_ts, '')::timestamptz, observation_end_ts=NULLIF(r.observation_end_ts, '')::timestamptz, price_provider=r.price_provider, provider_interval=r.provider_interval, metadata_json=r.metadata_json FROM r WHERE st.id=r.id;""")

    def fail_tracking(self, record: SignalTrackingRecord, *, status: str, error: str, retry_count: int | None = None) -> None:
        err = error.replace("'", "''")
        self._run(f"UPDATE signal_tracking SET status='{status}', error='{err}', retry_count={int(record.retry_count + 1 if retry_count is None else retry_count)}, updated_at=now() WHERE id={int(record.id or 0)};")

    def backtest_summaries(self, *, period_start: datetime, period_end: datetime, min_samples: int = 5) -> list[BacktestSummary]:
        ps, pe = _iso(period_start).replace("'", "''"), _iso(period_end).replace("'", "''")
        data = json.loads((self._run(f"""SELECT COALESCE(jsonb_agg(row_to_json(t)), '[]'::jsonb)::text FROM (
          SELECT kind, window_minutes, count(*)::int AS total, sum(CASE WHEN success THEN 1 ELSE 0 END)::int AS wins,
          sum(CASE WHEN success IS NOT NULL THEN 1 ELSE 0 END)::int AS directional_total,
          avg(coalesce(return_pct,0)) AS avg_return_pct, avg(coalesce(max_runup_pct,0)) AS avg_max_runup_pct, avg(coalesce(max_drawdown_pct,0)) AS avg_max_drawdown_pct,
          sum(CASE WHEN (metadata_json->>'is_outlier')::boolean THEN 1 ELSE 0 END)::int AS outlier_count
          FROM signal_tracking WHERE status='completed' AND signal_ts >= '{ps}'::timestamptz AND signal_ts < '{pe}'::timestamptz GROUP BY kind, window_minutes ORDER BY window_minutes ASC, count(*) DESC
        ) t;""").strip() or "[]"))
        return [BacktestSummary(kind=r["kind"], window_minutes=int(r["window_minutes"]), total=int(r["total"]), wins=int(r.get("wins") or 0), directional_total=int(r.get("directional_total") or 0), avg_return_pct=float(r.get("avg_return_pct") or 0), avg_max_runup_pct=float(r.get("avg_max_runup_pct") or 0), avg_max_drawdown_pct=float(r.get("avg_max_drawdown_pct") or 0), min_samples=min_samples, outlier_count=int(r.get("outlier_count") or 0)) for r in data]

    def set_provider_cooldown(self, provider: str, blocked_until: datetime, *, reason: str = "", retry_count: int = 1) -> None:
        p, r = provider.replace("'", "''"), reason.replace("'", "''")
        self._run(f"INSERT INTO provider_cooldowns(provider, blocked_until, reason, retry_count) VALUES ('{p}', '{_iso(blocked_until)}'::timestamptz, '{r}', {int(retry_count)}) ON CONFLICT(provider) DO UPDATE SET blocked_until=excluded.blocked_until, reason=excluded.reason, retry_count=excluded.retry_count, updated_at=now();")

    def is_provider_blocked(self, provider: str, now: datetime) -> bool:
        p = provider.replace("'", "''")
        return (self._run(f"SELECT CASE WHEN EXISTS(SELECT 1 FROM provider_cooldowns WHERE provider='{p}' AND blocked_until > '{_iso(now)}'::timestamptz) THEN '1' ELSE '0' END;").strip() == "1")

    def record_review_send(self, period_start: datetime, period_end: datetime, channel: str, content_hash: str, *, force: bool = False, metadata: dict | None = None) -> bool:
        ps, pe, ch, h = _iso(period_start), _iso(period_end), channel.replace("'", "''"), content_hash.replace("'", "''")
        if force:
            self._run(f"DELETE FROM review_sends WHERE period_start='{ps}'::timestamptz AND period_end='{pe}'::timestamptz AND channel='{ch}';")
        safe_meta = json.dumps(metadata or {}, ensure_ascii=False).replace("'", "''")
        out = self._run(f"WITH ins AS (INSERT INTO review_sends(period_start, period_end, channel, content_hash, metadata_json) VALUES ('{ps}'::timestamptz, '{pe}'::timestamptz, '{ch}', '{h}', '{safe_meta}'::jsonb) ON CONFLICT(period_start, period_end, channel) DO NOTHING RETURNING 1) SELECT count(*) FROM ins;").strip()
        return int(out or 0) > 0
