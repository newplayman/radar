# 庄家雷达 / Banker Radar v0.4

`庄家雷达` 是一个加密市场异动监控与解释系统：结合 Binance/OKX 合约公开数据、Binance Web3/GMGN 链上 Smart Money 信号、Telegram 播报，以及 v0.4 的信号追踪/回测复盘。

> 当前版本只做异动监控与解释，不做自动交易；输出不是投资建议。

## 已实现

- 收筹池分析：长期横盘、低成交、窄区间、低斜率。
- Binance USDT 永续公共数据：日线 K、24h ticker、funding、OI 变化。
- OKX OI 变化榜：通过 `okx market oi-change --json` 接入。
- 信号评分：
  - `暗流吸筹`：收筹池内 OI 上升但价格基本没动。
  - `空头燃料`：价格上涨但资金费率为负，存在轧空燃料。
  - `综合异动`：兜底 OI/价格/成交量异动。
- PostgreSQL 落库：生产运行统一写入 `DATABASE_URL` 指向的 PostgreSQL。
- Telegram 风格报告格式。
- Telegram v0.2：
  - `telegram-send`：扫描后推送到指定 Telegram chat。
  - `telegram-schedule`：按间隔定时扫描并推送。
  - `telegram-bot`：长轮询处理 `@提及` 查询。
  - 群组内默认 `require_mention=true`，只响应 @bot 的消息。
- Smart Money v0.3：
  - Binance Web3 Smart Money 解析与 GMGN CLI fallback。
  - 免费/订阅额度保护：低频采样、provider cooldown、自恢复、链上模块失败时降级为纯合约雷达。
  - Token Audit 高风险过滤，拦截 honeypot/高风险权限的正向榜单。
  - 新增 `🧠 链上聪明钱榜` 与 `🧬 链上链下共振榜`。
- PostgreSQL JSONB 是唯一生产存储；SQLite 仅用于单元测试或显式本地临时验证。
- Signal Tracking v0.4：15m/1h/4h/24h 信号追踪、回测统计、每日 Telegram 复盘。
- 单元测试覆盖 CLI、配置、Telegram、评分、限流 fallback、formatter、存储、追踪/回测等核心逻辑。

## 项目文档

- [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md)：新对话/新 Agent 接手项目时的上下文交接文档。
- [ROADMAP.md](ROADMAP.md)：里程碑、后续版本规划和非目标。
- [CHANGELOG.md](CHANGELOG.md)：版本变更记录。

## 安装/运行

```bash
git clone https://github.com/newplayman/radar.git
cd radar
python3 -m pip install -e . --break-system-packages
python3 -m pytest -q
```

生产运行前，确保 `/root/banker-radar/.env` 或当前环境中有：

```bash
# 示例：把实际连接串放入 .env，不要提交到 git
DATABASE_URL='<your-postgres-connection-string>'
```

常用命令：

```bash
# 默认扫描：Binance top symbols + OKX OI榜 + Smart Money增强
banker-radar scan

# 指定币种扫描
banker-radar scan --symbols BTCUSDT,ETHUSDT,SOLUSDT

# 免费额度紧张/链上 API 限流时，强制只跑合约雷达
banker-radar scan --no-smart-money
```

如需临时本地测试 SQLite，必须显式使用测试配置或把配置改为 `storage.backend: sqlite`，不要在生产中混用两套库。

## Telegram 使用

优先使用环境变量配置，避免把 token 写进仓库：

```bash
export TELEGRAM_BOT_TOKEN='***'
export TELEGRAM_CHAT_ID='-100xxxxxxxxxx'
export TELEGRAM_BOT_USERNAME='ctb007_bot'
export TELEGRAM_REQUIRE_MENTION=true
```

也可以写入 `configs/radar.yaml` 的 `telegram` 段。

### 手动推送一次

```bash
banker-radar telegram-send

# 不实际发送，只打印推送内容
banker-radar telegram-send --dry-run
```

### 定时推送

```bash
# 每 60 分钟推送一次，间隔可由 configs/radar.yaml telegram.interval_minutes 控制
banker-radar telegram-schedule

# 只跑一轮，用于 systemd/cron 测试
banker-radar telegram-schedule --once
```

### @提及查询

```bash
banker-radar telegram-bot
```

支持命令：

```text
@ctb007_bot 庄家雷达
@ctb007_bot 今日异动
@ctb007_bot 分析 APE
@ctb007_bot 帮助
```

注意：如果同一个 Telegram bot token 已经被 Hermes gateway 用 `getUpdates` 轮询，不能同时启动本项目的 `telegram-bot` 长轮询，否则 Telegram 会报 polling conflict。`telegram-send` 和 `telegram-schedule` 只调用 `sendMessage`，不会与 Hermes gateway 轮询冲突。

## v0.4 信号追踪与复盘

```bash
# 将近期信号加入追踪队列，并处理已到期窗口
banker-radar track-signals

# 打印昨日复盘，不发送 Telegram
banker-radar backtest-report --period yesterday

# 发送昨日复盘；默认幂等，同一周期/频道只发一次
banker-radar telegram-review --period yesterday

# 如需重发
banker-radar telegram-review --period yesterday --force
```

复盘仅统计信号出现后价格表现，不代表真实交易收益；未计滑点、手续费、成交可得性。systemd 模板见 `deploy/systemd/`。

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

smart_money:
  enabled: true
  limit: 30
  provider_order: [binance_web3, gmgn]
  allowed_chains: [sol, bsc, base, eth]
  max_audits_per_scan: 5

storage:
  backend: postgres
  postgres:
    url_env: DATABASE_URL
    psql_path: psql

telegram:
  bot_token: ""
  chat_id: ""
  bot_username: "ctb007_bot"
  require_mention: true
  interval_minutes: 60
```

SQLite 只用于测试/临时本地验证，生产不要开启：

```yaml
storage:
  backend: sqlite
  sqlite:
    path: data/radar.db
```

## v0.3/v0.4 限流与自恢复策略

- Binance Web3 优先，GMGN 次级；任一 provider 报 `429/rate limit/too many requests` 会进入 cooldown。
- cooldown 期间自动跳过该 provider，后续按时间自恢复，不影响 OKX/Binance 合约扫描。
- `smart_money.limit` 与 `max_audits_per_scan` 默认偏保守，避免免费/订阅额度被一次扫描打满。
- `--no-smart-money` 可作为紧急降级开关，Telegram 推送和查询仍能输出合约雷达。
- v0.4 tracking 使用请求预算、幂等 tracking 记录、review_sends 去重，避免重复请求和重复复盘推送。

## 下一步 v0.5

1. OKX/Binance 同币种共振合并，避免重复并提升可信度。
2. 更细的单币分析：盘口、主动成交、大单、观察位。
3. watchlist 和单币观察位/失效条件。
