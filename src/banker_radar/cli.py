from __future__ import annotations

import argparse
from pathlib import Path

from banker_radar.alerts.formatter import format_report
from banker_radar.collectors.binance_futures import fetch_features, fetch_klines, fetch_top_usdt_symbols
from banker_radar.collectors.okx_market import fetch_oi_change as fetch_okx_oi_change
from banker_radar.config import load_config
from banker_radar.engines.accumulation import analyze_accumulation
from banker_radar.signals.scoring import score_market
from banker_radar.storage.sqlite import RadarStore


def run_scan(config_path: str, db_path: str, symbols: list[str] | None = None) -> str:
    cfg = load_config(config_path)
    top_n = int(cfg.get("alerts", {}).get("top_n", 5))
    min_score = int(cfg.get("alerts", {}).get("min_score", 60))
    binance_limit = int(cfg.get("scan", {}).get("binance_limit", 30))
    acc_cfg = cfg.get("accumulation", {})

    symbols = symbols or fetch_top_usdt_symbols(binance_limit)
    accum = {}
    for symbol in symbols:
        try:
            candles = fetch_klines(symbol, "1d", max(int(acc_cfg.get("min_sideways_days", 45)), 60))
            accum[symbol] = analyze_accumulation(symbol, candles, **acc_cfg)
        except Exception:
            accum[symbol] = None

    features = fetch_features(symbols)
    signals = [score_market(f, accum.get(f.symbol)) for f in features]

    # OKX 作为 v0.1 的跨交易所异动补充：直接读取 OI 变化榜，先不做收筹池匹配。
    okx_limit = int(cfg.get("scan", {}).get("okx_limit", 20))
    min_oi_usd = float(cfg.get("oi", {}).get("min_oi_usd", 0))
    try:
        okx_features = fetch_okx_oi_change(limit=okx_limit, min_oi_usd=min_oi_usd)
        signals.extend(score_market(f, None) for f in okx_features)
    except Exception:
        pass

    signals = [s for s in signals if s.score >= min_score]
    signals.sort(key=lambda s: s.score, reverse=True)
    signals = signals[: max(top_n * 3, top_n)]

    store = RadarStore(db_path)
    store.init()
    for s in signals:
        store.save_signal(s)
    return format_report(signals, title="庄家雷达 v0.1 扫描")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="庄家雷达 v0.1")
    parser.add_argument("scan", nargs="?", default="scan", help="run scan")
    parser.add_argument("--config", default="configs/radar.yaml")
    parser.add_argument("--db", default="data/radar.db")
    parser.add_argument("--symbols", default="", help="comma separated Binance futures symbols, e.g. SAGAUSDT,REDUSDT")
    args = parser.parse_args(argv)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or None
    print(run_scan(args.config, args.db, symbols))


if __name__ == "__main__":
    main()
