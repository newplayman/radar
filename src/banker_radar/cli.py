from __future__ import annotations

import argparse
import os
import time
from dataclasses import replace

from banker_radar.alerts.formatter import format_report
from banker_radar.alerts.telegram import TelegramClient
from banker_radar.collectors.binance_futures import fetch_features, fetch_klines, fetch_top_usdt_symbols
from banker_radar.collectors.binance_web3 import BinanceWeb3Collector
from banker_radar.collectors.chain import collect_chain_features
from banker_radar.collectors.gmgn import GMGNCollector
from banker_radar.collectors.okx_market import fetch_oi_change as fetch_okx_oi_change
from banker_radar.config import load_config
from banker_radar.engines.accumulation import analyze_accumulation
from banker_radar.signals.resonance import build_resonance_signals
from banker_radar.signals.scoring import score_market
from banker_radar.signals.smart_money import score_chain_features
from banker_radar.storage import create_store
from banker_radar.telegram.bot import TelegramRadarBot
from banker_radar.utils.rate_limit import ProviderHealth

_CHAIN_PROVIDER_HEALTH: dict[str, ProviderHealth] = {
    "binance_web3_provider": ProviderHealth(max_failures=1, cooldown_seconds=900),
    "gmgn_provider": ProviderHealth(max_failures=2, cooldown_seconds=300),
}


def _collect_smart_money_signals(cfg: dict, *, disabled: bool = False):
    sm_cfg = cfg.get("smart_money", {})
    if disabled or not bool(sm_cfg.get("enabled", True)):
        return []

    chains = sm_cfg.get("allowed_chains") or ["sol", "bsc", "base", "eth"]
    limit = int(sm_cfg.get("limit", 30))
    timeout = int(sm_cfg.get("timeout_seconds", cfg.get("gmgn", {}).get("timeout_seconds", 20)))
    provider_order = sm_cfg.get("provider_order") or ["binance_web3", "gmgn"]
    providers = []
    collectors = {}

    if "binance_web3" in provider_order:
        binance = BinanceWeb3Collector(timeout_seconds=timeout)
        collectors["binance_web3"] = binance

        def binance_web3_provider():
            return binance.fetch_smart_money(chains, limit=limit)

        providers.append(binance_web3_provider)

    if "gmgn" in provider_order and cfg.get("gmgn", {}).get("enabled", True):
        gmgn_cfg = cfg.get("gmgn", {})
        gmgn = GMGNCollector(cli_path=gmgn_cfg.get("cli_path", "gmgn-cli"), timeout_seconds=int(gmgn_cfg.get("timeout_seconds", timeout)))
        collectors["gmgn"] = gmgn

        def gmgn_provider():
            return gmgn.fetch_smart_money(chains, limit=int(gmgn_cfg.get("smartmoney_limit", limit)))

        providers.append(gmgn_provider)

    features = collect_chain_features(providers, health=_CHAIN_PROVIDER_HEALTH)
    max_audits = int(sm_cfg.get("max_audits_per_scan", 5))
    if max_audits > 0:
        enriched = []
        used = 0
        for feature in features:
            if used < max_audits and feature.token_address and feature.provider in collectors:
                try:
                    audit = collectors[feature.provider].fetch_audit(feature.chain, feature.token_address)
                    feature = replace(feature, audit=audit)
                    used += 1
                except Exception:
                    pass
            enriched.append(feature)
        features = enriched
    chain_signals = score_chain_features(
        features,
        min_score=int(sm_cfg.get("min_score", 60)),
        min_smart_wallets=int(sm_cfg.get("min_smart_wallets", 2)),
        max_exit_rate_pct=float(sm_cfg.get("max_exit_rate_pct", 50)),
        max_gain_pct_for_fresh_signal=float(sm_cfg.get("max_gain_pct_for_fresh_signal", 80)),
    )
    return chain_signals


def run_scan(config_path: str, db_path: str, symbols: list[str] | None = None, *, title: str = "庄家雷达 v0.3 扫描", no_smart_money: bool = False) -> str:
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

    # OKX 作为跨交易所异动补充；单币分析时仍保留 OKX 榜单，便于看到全市场强信号。
    okx_limit = int(cfg.get("scan", {}).get("okx_limit", 20))
    min_oi_usd = float(cfg.get("oi", {}).get("min_oi_usd", 0))
    try:
        okx_features = fetch_okx_oi_change(limit=okx_limit, min_oi_usd=min_oi_usd)
        signals.extend(score_market(f, None) for f in okx_features)
    except Exception:
        pass

    contract_signals = [s for s in signals if s.score >= min_score]
    chain_signals = _collect_smart_money_signals(cfg, disabled=no_smart_money)
    resonance_signals = build_resonance_signals(contract_signals, chain_signals, min_score=int(cfg.get("resonance", {}).get("min_score", 75)))

    signals = contract_signals + chain_signals + resonance_signals
    signals = [s for s in signals if s.score >= min_score or s.kind in {"链上聪明钱", "链上链下共振"}]
    signals.sort(key=lambda s: s.score, reverse=True)
    signals = signals[: max(top_n * 5, top_n)]

    store = create_store(cfg, db_path=db_path)
    store.init()
    for s in signals:
        store.save_signal(s)
    return format_report(signals, title=title)


def _telegram_config(cfg: dict, args: argparse.Namespace) -> tuple[str, str | None, str, bool, int]:
    tg_cfg = cfg.get("telegram", {})
    token = args.telegram_token or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or tg_cfg.get("bot_token", "")
    chat_id = args.telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID") or tg_cfg.get("chat_id")
    username = args.bot_username or os.getenv("TELEGRAM_BOT_USERNAME") or tg_cfg.get("bot_username", "ctb007_bot")
    require_mention = str(os.getenv("TELEGRAM_REQUIRE_MENTION", tg_cfg.get("require_mention", True))).lower() in {"1", "true", "yes", "on"}
    interval = int(args.interval_minutes or tg_cfg.get("interval_minutes", 60))
    return token, chat_id, username, require_mention, interval


def run_telegram_send(config_path: str, db_path: str, args: argparse.Namespace) -> str:
    cfg = load_config(config_path)
    token, chat_id, _, _, _ = _telegram_config(cfg, args)
    symbols = [s.strip().upper() for s in getattr(args, "symbols", "").split(",") if s.strip()] or None
    report = run_scan(config_path, db_path, symbols, title="庄家雷达 v0.3 Telegram 推送", no_smart_money=getattr(args, "no_smart_money", False))
    if getattr(args, "dry_run", False):
        return report
    if not token or not chat_id:
        raise SystemExit("缺少 Telegram 配置：请设置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID，或 configs/radar.yaml telegram.*")
    TelegramClient(token=token, chat_id=chat_id).send_message(report)
    return "Telegram 推送完成。"


def run_telegram_schedule(config_path: str, db_path: str, args: argparse.Namespace) -> None:
    cfg = load_config(config_path)
    token, chat_id, _, _, interval_minutes = _telegram_config(cfg, args)
    if not token or not chat_id:
        raise SystemExit("缺少 Telegram 配置：请设置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID，或 configs/radar.yaml telegram.*")
    client = TelegramClient(token=token, chat_id=chat_id)
    while True:
        report = run_scan(config_path, db_path, None, title="庄家雷达 v0.3 定时扫描", no_smart_money=getattr(args, "no_smart_money", False))
        client.send_message(report)
        if getattr(args, "once", False):
            return
        time.sleep(interval_minutes * 60)


def run_telegram_bot(config_path: str, db_path: str, args: argparse.Namespace) -> None:
    cfg = load_config(config_path)
    token, _, username, require_mention, _ = _telegram_config(cfg, args)
    if not token:
        raise SystemExit("缺少 Telegram 配置：请设置 TELEGRAM_BOT_TOKEN，或 configs/radar.yaml telegram.bot_token")
    client = TelegramClient(token=token)

    def scan_fn(symbols: list[str] | None) -> str:
        title = "庄家雷达 v0.3 单币分析" if symbols else "庄家雷达 v0.3 即时扫描"
        return run_scan(config_path, db_path, symbols, title=title, no_smart_money=getattr(args, "no_smart_money", False))

    bot = TelegramRadarBot(
        bot_username=username,
        require_mention=require_mention,
        scan_fn=scan_fn,
        send_fn=lambda chat_id, text: client.send_message(text, chat_id=chat_id),
    )

    offset: int | None = None
    while True:
        updates = client.get_updates(offset=offset, timeout=30)
        next_offset = bot.handle_updates(updates)
        if next_offset is not None:
            offset = next_offset
        if getattr(args, "once", False):
            return
        time.sleep(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="庄家雷达 v0.3")
    parser.add_argument("command", nargs="?", default="scan", choices=["scan", "telegram-send", "telegram-schedule", "telegram-bot"], help="command to run")
    parser.add_argument("--config", default="configs/radar.yaml")
    parser.add_argument("--db", default="data/radar.db")
    parser.add_argument("--symbols", default="", help="comma separated Binance futures symbols, e.g. SAGAUSDT,REDUSDT")
    parser.add_argument("--telegram-token", default="")
    parser.add_argument("--telegram-chat-id", default="")
    parser.add_argument("--bot-username", default="")
    parser.add_argument("--interval-minutes", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--once", action="store_true", help="run one schedule/bot iteration then exit")
    parser.add_argument("--no-smart-money", action="store_true", help="disable Binance Web3/GMGN chain enrichment for this run")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or None
    if args.command == "scan":
        print(run_scan(args.config, args.db, symbols, no_smart_money=args.no_smart_money))
    elif args.command == "telegram-send":
        print(run_telegram_send(args.config, args.db, args))
    elif args.command == "telegram-schedule":
        run_telegram_schedule(args.config, args.db, args)
    elif args.command == "telegram-bot":
        run_telegram_bot(args.config, args.db, args)


if __name__ == "__main__":
    main()
