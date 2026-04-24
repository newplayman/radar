# Changelog

All notable changes to Banker Radar are documented here.

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
