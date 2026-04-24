from __future__ import annotations

import pytest

from banker_radar.cli import build_parser
from banker_radar.storage import create_store
from banker_radar.storage.postgres import PostgresRadarStore
from banker_radar.storage.sqlite import RadarStore


def test_runtime_storage_defaults_to_postgres_from_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@127.0.0.1:5433/banker_radar")

    store = create_store({})

    assert isinstance(store, PostgresRadarStore)
    assert store.url.startswith("postgresql://")


def test_postgres_backend_without_database_url_does_not_fallback_to_sqlite(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_store({"storage": {"backend": "postgres", "postgres": {"url_env": "DATABASE_URL"}}}, db_path=str(tmp_path / "should-not-exist.db"))


def test_sqlite_is_only_available_when_explicitly_requested(tmp_path):
    store = create_store({"storage": {"backend": "sqlite", "sqlite": {"path": str(tmp_path / "test.db")}}})

    assert isinstance(store, RadarStore)


def test_cli_db_argument_is_not_a_runtime_default():
    parser = build_parser()
    args = parser.parse_args(["scan"])

    assert args.db == ""
