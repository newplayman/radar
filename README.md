# 庄家雷达 / Banker Radar v0.2

MVP 目标：把 `accumulation-radar` 的“收筹池 + 暗流信号 + 轧空榜”思路模块化，并接入当前机器上的 Binance 公共合约数据、OKX CLI 公共市场数据，以及 Telegram 推送/查询入口。

> 当前版本只做异动监控与解释，不做自动交易；输出不是投资建议。

## 已实现

- 收筹池分析：长期横盘、低成交、窄区间、低斜率。
- Binance USDT 永续公共数据：日线 K、24h ticker、funding、OI 变化。
- OKX OI 变化榜：通过 `okx market oi-change --json` 接入。
- 信号评分：
  - `暗流吸筹`：收筹池内 OI 上升但价格基本没动。
  - `空头燃料`：价格上涨但资金费率为负，存在轧空燃料。
  - `综合异动`：兜底 OI/价格/成交量异动。
- SQLite 落库：`data/radar.db`。
- Telegram 风格报告格式。
- Telegram v0.2：
  - `telegram-send`：扫描后推送到指定 Telegram chat。
  - `telegram-schedule`：按间隔定时扫描并推送。
  - `telegram-bot`：长轮询处理 `@提及` 查询。
  - 群组内默认 `require_mention=true`，只响应 @bot 的消息。
- 单元测试：12 个。

## 安装/运行

```bash
cd /root/banker-radar
python3 -m pip install -e . --break-system-packages
python3 -m pytest -q

# 指定币种测试扫描
banker-radar scan --symbols BTCUSDT,ETHUSDT,SOLUSDT --db data/test-radar.db

# 默认扫描：Binance top symbols + OKX OI榜
banker-radar scan --db data/radar.db
```

## Telegram 使用

优先使用环境变量配置，避免把 token 写进仓库：

```bash
export TELEGRAM_BOT_TOKEN='xxx'
export TELEGRAM_CHAT_ID='-100xxxxxxxxxx'
export TELEGRAM_BOT_USERNAME='ctb007_bot'
export TELEGRAM_REQUIRE_MENTION=true
```

也可以写入 `configs/radar.yaml` 的 `telegram` 段。

### 手动推送一次

```bash
banker-radar telegram-send --db data/radar.db

# 不实际发送，只打印推送内容
banker-radar telegram-send --dry-run --db data/radar.db
```

### 定时推送

```bash
# 每 60 分钟推送一次，间隔可由 configs/radar.yaml telegram.interval_minutes 控制
banker-radar telegram-schedule --db data/radar.db

# 只跑一轮，用于 systemd/cron 测试
banker-radar telegram-schedule --once --db data/radar.db
```

### @提及查询

```bash
banker-radar telegram-bot --db data/radar.db
```

支持命令：

```text
@ctb007_bot 庄家雷达
@ctb007_bot 今日异动
@ctb007_bot 分析 APE
@ctb007_bot 帮助
```

注意：如果同一个 Telegram bot token 已经被 Hermes gateway 用 `getUpdates` 轮询，不能同时启动本项目的 `telegram-bot` 长轮询，否则 Telegram 会报 polling conflict。`telegram-send` 和 `telegram-schedule` 只调用 `sendMessage`，不会与 Hermes gateway 轮询冲突。

## 配置

配置文件：`configs/radar.yaml`

关键项：

```yaml
scan:
  binance_limit: 40
  okx_limit: 40

alerts:
  min_score: 60
  top_n: 5

telegram:
  bot_token: ""
  chat_id: ""
  bot_username: "ctb007_bot"
  require_mention: true
  interval_minutes: 60
```

## 下一步 v0.3

1. Binance Web3 Smart Money 榜接入。
2. 信号落库后的 15m/1h/4h/24h 追踪回测。
3. OKX/Binance 同币种共振合并，避免重复并提升可信度。
4. 更细的单币分析：盘口、主动成交、大单、观察位。
