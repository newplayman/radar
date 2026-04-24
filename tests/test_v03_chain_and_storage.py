from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from banker_radar.collectors.binance_web3 import parse_smart_money_response
from banker_radar.collectors.chain import collect_chain_features
from banker_radar.collectors.gmgn import GMGNCollector, parse_gmgn_smartmoney
from banker_radar.models import ChainSignalFeature, RadarSignal, TokenAuditResult
from banker_radar.signals.resonance import build_resonance_signals
from banker_radar.signals.smart_money import score_chain_feature
from banker_radar.storage import create_store
from banker_radar.storage.postgres import PostgresRadarStore
from banker_radar.storage.sqlite import RadarStore
from banker_radar.utils.rate_limit import ProviderHealth


def test_radar_signal_preserves_metadata_when_timestamped():
    s = RadarSignal(
        symbol="TESTUSDT",
        kind="链上聪明钱",
        score=88,
        reason="3 个聪明钱地址买入",
        risk="中",
        source="gmgn",
        metadata={"chain": "sol", "provider": "gmgn"},
    )

    stamped = s.with_timestamp()

    assert stamped.created_at
    assert stamped.metadata == {"chain": "sol", "provider": "gmgn"}


def test_sqlite_store_migrates_and_round_trips_metadata(tmp_path: Path):
    db_path = tmp_path / "radar.db"
    store = RadarStore(db_path)
    store.init()
    signal = RadarSignal("ABCUSDT", "链上聪明钱", 77, "reason", "中", "gmgn", metadata={"address": "0xabc"})

    store.save_signal(signal)
    latest = store.latest_signals(1)[0]

    assert latest.metadata == {"address": "0xabc"}
    with sqlite3.connect(db_path) as db:
        cols = [r[1] for r in db.execute("PRAGMA table_info(signals)").fetchall()]
    assert "metadata_json" in cols


def test_create_store_selects_sqlite_for_tests(tmp_path: Path):
    store = create_store({"storage": {"backend": "sqlite", "sqlite": {"path": str(tmp_path / "x.db")}}})
    assert isinstance(store, RadarStore)


def test_create_store_selects_postgres_from_env(monkeypatch):
    monkeypatch.setenv("BANKER_RADAR_DATABASE_URL", "postgresql://user:pass@127.0.0.1:5433/banker_radar")
    store = create_store({"storage": {"backend": "postgres", "postgres": {"url_env": "BANKER_RADAR_DATABASE_URL", "psql_path": "/usr/bin/psql"}}})
    assert isinstance(store, PostgresRadarStore)
    assert store.url.startswith("postgresql://")
    assert store.psql_path == "/usr/bin/psql"


def test_provider_health_enters_cooldown_after_rate_limit_and_recovers_by_time():
    health = ProviderHealth(max_failures=2, cooldown_seconds=10)
    assert health.available(now=100)

    health.record_failure("rate_limited", now=100)
    assert health.available(now=101)
    health.record_failure("rate_limited", now=102)

    assert not health.available(now=105)
    assert health.available(now=113)
    health.record_success()
    assert health.available(now=113)


def test_parse_binance_web3_smart_money_response_normalizes_fields():
    raw = {
        "success": True,
        "code": "000000",
        "data": [
            {
                "ticker": "abc",
                "chainId": "CT_501",
                "contractAddress": "So111",
                "smartMoneyCount": 4,
                "direction": "buy",
                "totalTokenValue": "1234.5",
                "exitRate": 12,
                "maxGain": "23.4",
                "status": "active",
                "tokenTag": {"Sensitive Events": [{"tagName": "Whale Buy"}]},
            }
        ],
    }

    features = parse_smart_money_response(raw, provider="binance_web3")

    assert len(features) == 1
    f = features[0]
    assert f.symbol == "ABCUSDT"
    assert f.chain == "sol"
    assert f.direction == "buy"
    assert f.smart_wallet_count == 4
    assert f.whale_count == 1
    assert f.exit_rate_pct == 12
    assert "Whale Buy" in f.tags


def test_parse_gmgn_smartmoney_tolerates_list_payload():
    raw = {
        "list": [
            {
                "symbol": "dogeai",
                "address": "addr1",
                "smart_money_count": 3,
                "side": "buy",
                "usd_value": 5000,
                "chain": "sol",
            }
        ]
    }

    features = parse_gmgn_smartmoney(raw, chain="sol")

    assert features[0].symbol == "DOGEAIUSDT"
    assert features[0].provider == "gmgn"
    assert features[0].token_address == "addr1"
    assert features[0].smart_wallet_count == 3


def test_gmgn_collector_returns_empty_on_timeout_without_raising():
    def runner(*args, **kwargs):
        raise TimeoutError("slow")

    collector = GMGNCollector(runner=runner, timeout_seconds=1)
    assert collector.fetch_smart_money(["sol"], limit=5) == []


def test_collect_chain_features_falls_back_from_failed_binance_to_gmgn():
    def binance_provider():
        raise RuntimeError("429 rate limited")

    def gmgn_provider():
        return [ChainSignalFeature(symbol="ABCUSDT", chain="sol", provider="gmgn", smart_wallet_count=2, direction="buy")]

    features = collect_chain_features([binance_provider, gmgn_provider])

    assert len(features) == 1
    assert features[0].provider == "gmgn"


def test_collect_chain_features_skips_provider_in_cooldown():
    called = {"blocked": 0, "fallback": 0}

    def blocked_provider():
        called["blocked"] += 1
        return [ChainSignalFeature(symbol="BADUSDT", chain="sol", provider="binance_web3")]

    def fallback_provider():
        called["fallback"] += 1
        return [ChainSignalFeature(symbol="OKUSDT", chain="sol", provider="gmgn", smart_wallet_count=2)]

    health = {
        "blocked_provider": ProviderHealth(max_failures=1, cooldown_seconds=30, failures=1, cooldown_until=9999999999),
        "fallback_provider": ProviderHealth(),
    }

    features = collect_chain_features([blocked_provider, fallback_provider], health=health)

    assert called == {"blocked": 0, "fallback": 1}
    assert features[0].symbol == "OKUSDT"


def test_score_chain_feature_blocks_high_risk_audit():
    feature = ChainSignalFeature(
        symbol="RISKUSDT",
        chain="bsc",
        provider="binance_web3",
        smart_wallet_count=9,
        direction="buy",
        audit=TokenAuditResult(chain="bsc", token_address="0x1", risk_level="HIGH", risk_score=5, is_supported=True, has_result=True),
    )

    signal = score_chain_feature(feature)

    assert signal is None


def test_score_chain_feature_creates_smart_money_signal_with_metadata():
    feature = ChainSignalFeature(
        symbol="ALPHAUSDT",
        chain="sol",
        provider="gmgn",
        token_address="addr",
        smart_wallet_count=5,
        whale_count=1,
        direction="buy",
        exit_rate_pct=10,
        max_gain_pct=20,
        tags=["Whale Buy"],
    )

    signal = score_chain_feature(feature)

    assert signal is not None
    assert signal.kind == "链上聪明钱"
    assert signal.score >= 70
    assert signal.metadata["provider"] == "gmgn"
    assert signal.metadata["smart_wallet_count"] == 5


def test_build_resonance_signals_upgrades_matching_contract_and_chain_signal():
    contract = RadarSignal("ALPHAUSDT", "空头燃料", 76, "OI +5%", "中高", "okx")
    chain = RadarSignal(
        "ALPHAUSDT",
        "链上聪明钱",
        80,
        "5 个聪明钱地址买入",
        "中",
        "gmgn",
        metadata={"chain": "sol"},
    )

    resonance = build_resonance_signals([contract], [chain])

    assert len(resonance) == 1
    assert resonance[0].kind == "链上链下共振"
    assert resonance[0].score > max(contract.score, chain.score)
    assert "Smart Money" in resonance[0].reason or "聪明钱" in resonance[0].reason
