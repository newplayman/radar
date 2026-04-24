from __future__ import annotations

import json
import urllib.request
from typing import Any

from banker_radar.models import ChainSignalFeature, TokenAuditResult

CHAIN_ID_TO_NAME = {"CT_501": "sol", "56": "bsc", "8453": "base", "1": "eth"}
NAME_TO_CHAIN_ID = {v: k for k, v in CHAIN_ID_TO_NAME.items()}


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
    if text.endswith("USDT"):
        return text
    return f"{text}USDT"


def _tags(token_tag: Any) -> list[str]:
    result: list[str] = []
    if isinstance(token_tag, dict):
        for entries in token_tag.values():
            if isinstance(entries, list):
                for item in entries:
                    if isinstance(item, dict) and item.get("tagName"):
                        result.append(str(item["tagName"]))
    return result


def parse_smart_money_response(raw: dict, *, provider: str = "binance_web3") -> list[ChainSignalFeature]:
    if not raw or raw.get("success") is False:
        return []
    rows = raw.get("data") or []
    if not isinstance(rows, list):
        return []
    features: list[ChainSignalFeature] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = _symbol(row.get("ticker") or row.get("symbol"))
        if not symbol:
            continue
        tags = _tags(row.get("tokenTag"))
        whale_count = sum(1 for t in tags if "whale" in t.lower())
        features.append(
            ChainSignalFeature(
                symbol=symbol,
                chain=CHAIN_ID_TO_NAME.get(str(row.get("chainId")), str(row.get("chainId") or "").lower()),
                provider=provider,
                token_address=str(row.get("contractAddress") or ""),
                direction=str(row.get("direction") or "").lower() or "buy",
                smart_wallet_count=_int(row.get("smartMoneyCount") or row.get("signalCount")),
                whale_count=whale_count,
                total_value_usd=_float(row.get("totalTokenValue")),
                exit_rate_pct=_float(row.get("exitRate")),
                max_gain_pct=_float(row.get("maxGain")),
                status=str(row.get("status") or ""),
                tags=tags,
                raw=row,
            )
        )
    return features


def parse_token_audit_response(raw: dict, *, chain: str, token_address: str) -> TokenAuditResult:
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        return TokenAuditResult(chain=chain, token_address=token_address, raw=raw or {})
    extra = data.get("extraInfo") or {}
    return TokenAuditResult(
        chain=chain,
        token_address=token_address,
        risk_level=str(data.get("riskLevelEnum") or "UNKNOWN"),
        risk_score=_int(data.get("riskLevel")),
        is_supported=bool(data.get("isSupported")),
        has_result=bool(data.get("hasResult")),
        buy_tax_pct=_float(extra.get("buyTax"), 0.0) if extra.get("buyTax") is not None else None,
        sell_tax_pct=_float(extra.get("sellTax"), 0.0) if extra.get("sellTax") is not None else None,
        raw=data,
    )


class BinanceWeb3Collector:
    def __init__(self, timeout_seconds: int = 20):
        self.timeout_seconds = timeout_seconds

    def fetch_smart_money(self, chains: list[str], limit: int = 50) -> list[ChainSignalFeature]:
        out: list[ChainSignalFeature] = []
        for chain in chains:
            chain_id = NAME_TO_CHAIN_ID.get(chain, chain)
            payload = json.dumps({"smartSignalType": "", "page": 1, "pageSize": min(limit, 100), "chainId": chain_id}).encode()
            req = urllib.request.Request(
                "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/web/signal/smart-money/ai",
                data=payload,
                headers={"Content-Type": "application/json", "Accept-Encoding": "identity", "User-Agent": "binance-web3/1.1 (Skill)"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:  # nosec - public endpoint
                raw = json.loads(resp.read().decode("utf-8"))
            out.extend(parse_smart_money_response(raw, provider="binance_web3"))
        return out

    def fetch_audit(self, chain: str, token_address: str) -> TokenAuditResult:
        import uuid

        chain_id = NAME_TO_CHAIN_ID.get(chain, chain)
        payload = json.dumps({"binanceChainId": chain_id, "contractAddress": token_address, "requestId": str(uuid.uuid4())}).encode()
        req = urllib.request.Request(
            "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/security/token/audit",
            data=payload,
            headers={"Content-Type": "application/json", "source": "agent", "Accept-Encoding": "identity", "User-Agent": "binance-web3/1.4 (Skill)"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:  # nosec - public endpoint
            raw = json.loads(resp.read().decode("utf-8"))
        return parse_token_audit_response(raw, chain=chain, token_address=token_address)
