from __future__ import annotations

import json
import subprocess

from banker_radar.models import MarketFeature


def _run_okx(args: list[str]) -> str:
    return subprocess.check_output(["okx", *args], text=True, timeout=30)


def parse_okx_oi_change(rows: list[dict]) -> list[MarketFeature]:
    out: list[MarketFeature] = []
    for r in rows:
        symbol = r.get("instId") or r.get("symbol")
        if not symbol:
            continue
        funding = float(r.get("fundingRate", 0) or 0)
        out.append(MarketFeature(
            symbol=symbol,
            price_change_pct=float(r.get("pxChgPct", r.get("chg24hPct", r.get("change24hPct", 0))) or 0),
            oi_delta_pct=float(r.get("oiDeltaPct", 0) or 0),
            funding_rate_pct=funding * (100 if abs(funding) < 1 else 1),
            volume_usd_24h=float(r.get("volUsd24h", 0) or 0),
            oi_usd=float(r.get("oiUsd", 0) or 0),
            source="okx",
        ))
    return out


def fetch_oi_change(limit: int = 20, bar: str = "1H", min_oi_usd: float = 0) -> list[MarketFeature]:
    # OKX CLI --json schema may evolve; v0.1 keeps this parser defensive.
    args = ["market", "oi-change", "--instType", "SWAP", "--bar", bar, "--sortBy", "oiDeltaPct", "--sortOrder", "desc", "--limit", str(limit), "--json"]
    if min_oi_usd:
        args += ["--minOiUsd", str(min_oi_usd)]
    raw = _run_okx(args)
    data = json.loads(raw)
    rows = data if isinstance(data, list) else data.get("data", [])
    return parse_okx_oi_change(rows)
