from __future__ import annotations

import json
import subprocess
from typing import Any, Callable

from banker_radar.models import ChainSignalFeature, TokenAuditResult


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _symbol(value: Any) -> str:
    text = str(value or "").strip().upper().replace("-", "")
    if not text:
        return ""
    return text if text.endswith("USDT") else f"{text}USDT"


def _rows(raw: Any) -> list[dict]:
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    if not isinstance(raw, dict):
        return []
    for key in ("list", "data", "items", "signals", "result"):
        value = raw.get(key)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
        if isinstance(value, dict):
            nested = _rows(value)
            if nested:
                return nested
    return []


def parse_gmgn_smartmoney(raw: Any, *, chain: str) -> list[ChainSignalFeature]:
    features: list[ChainSignalFeature] = []
    for row in _rows(raw):
        symbol = _symbol(row.get("symbol") or row.get("token_symbol") or row.get("ticker") or row.get("base_symbol"))
        if not symbol:
            continue
        tags = []
        raw_tags = row.get("tags") or row.get("tag") or []
        if isinstance(raw_tags, list):
            tags = [str(t) for t in raw_tags]
        elif raw_tags:
            tags = [str(raw_tags)]
        features.append(
            ChainSignalFeature(
                symbol=symbol,
                chain=str(row.get("chain") or chain),
                provider="gmgn",
                token_address=str(row.get("address") or row.get("token_address") or row.get("contract_address") or ""),
                direction=str(row.get("side") or row.get("direction") or "buy").lower(),
                smart_wallet_count=_int(row.get("smart_money_count") or row.get("smartMoneyCount") or row.get("smart_count") or row.get("wallet_count"), 1),
                whale_count=_int(row.get("whale_count") or row.get("whaleCount"), 0),
                total_value_usd=_float(row.get("usd_value") or row.get("value_usd") or row.get("amount_usd") or row.get("total_value_usd")),
                exit_rate_pct=_float(row.get("exit_rate") or row.get("exitRate")),
                max_gain_pct=_float(row.get("max_gain") or row.get("maxGain")),
                status=str(row.get("status") or ""),
                tags=tags,
                raw=row,
            )
        )
    return features


def parse_gmgn_security(raw: Any, *, chain: str, token_address: str) -> TokenAuditResult:
    data = raw.get("data", raw) if isinstance(raw, dict) else {}
    level = str(data.get("riskLevel") or data.get("risk_level") or data.get("risk") or "UNKNOWN").upper()
    score = _int(data.get("riskScore") or data.get("risk_score") or data.get("risk_level_num"))
    honeypot = bool(data.get("honeypot") or data.get("is_honeypot") or data.get("cannot_sell"))
    if honeypot:
        level = "HIGH"
        score = max(score, 5)
    return TokenAuditResult(chain=chain, token_address=token_address, risk_level=level, risk_score=score, is_supported=bool(data), has_result=bool(data), raw=data)


class GMGNCollector:
    def __init__(self, cli_path: str = "gmgn-cli", timeout_seconds: int = 20, runner: Callable[..., Any] | None = None):
        self.cli_path = cli_path
        self.timeout_seconds = timeout_seconds
        self.runner = runner or subprocess.run

    def _run_json(self, args: list[str]) -> Any:
        result = self.runner(args, capture_output=True, text=True, timeout=self.timeout_seconds, check=False)
        if getattr(result, "returncode", 0) != 0:
            raise RuntimeError(getattr(result, "stderr", "gmgn-cli failed"))
        return json.loads(getattr(result, "stdout", "") or "{}")

    def fetch_smart_money(self, chains: list[str], limit: int = 100, side: str = "buy") -> list[ChainSignalFeature]:
        out: list[ChainSignalFeature] = []
        for chain in chains:
            try:
                raw = self._run_json([self.cli_path, "track", "smartmoney", "--chain", chain, "--limit", str(limit), "--side", side, "--raw"])
                out.extend(parse_gmgn_smartmoney(raw, chain=chain))
            except Exception:
                continue
        return out

    def fetch_audit(self, chain: str, token_address: str) -> TokenAuditResult:
        raw = self._run_json([self.cli_path, "token", "security", "--chain", chain, "--address", token_address, "--raw"])
        return parse_gmgn_security(raw, chain=chain, token_address=token_address)
