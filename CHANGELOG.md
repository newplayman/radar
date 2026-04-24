# Changelog

All notable changes to Banker Radar are documented here.

## v0.3.0

### Added

- Binance Web3 Smart Money collector and parser.
- GMGN CLI Smart Money fallback and token security parser.
- Provider fallback with cooldown/backoff for free-tier/subscription rate limits.
- Chain Smart Money scoring with high-risk Token Audit blocking.
- Chain/contract resonance signals and Telegram sections:
  - `🧠 链上聪明钱榜`
  - `🧬 链上链下共振榜`
- PostgreSQL JSONB storage backend via `psql`, with SQLite fallback/test backend retained.
- `--no-smart-money` CLI flag for emergency degradation to pure contract radar.
- v0.3 unit tests for collectors, rate-limit recovery, scoring, resonance, formatter, CLI flag, and storage factory.

### Notes

- Smart Money enrichment is intentionally non-critical: if Binance Web3/GMGN is limited or unavailable, OKX/Binance contract radar continues to run.
- Default sampling limits are conservative to protect free or subscribed API/skill quotas.

## v0.2.0

### Added

- Telegram push command: `banker-radar telegram-send`.
- Telegram scheduled push command: `banker-radar telegram-schedule`.
- Telegram @mention query bot: `banker-radar telegram-bot`.
- `.env` auto-loading for local deployment secrets.
- Bot command parsing tests for group mention behavior.

### Notes

- Telegram tokens and chat IDs must be supplied through environment variables or a local `.env` file; `.env` is intentionally ignored by git.
- If a bot token is already used by another `getUpdates` poller, do not start `telegram-bot` with the same token.

## v0.1.0

### Added

- Initial modular project structure.
- Binance USDT perpetual public market collector.
- OKX public OI-change collector through OKX CLI.
- Accumulation pool detection.
- Signal scoring for:
  - 暗流吸筹
  - 空头燃料
  - 综合异动
- SQLite storage.
- Telegram-style report formatter.
- Unit tests for the MVP core.
