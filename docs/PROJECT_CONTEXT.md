# 庄家雷达 / Banker Radar 项目上下文

> 给新对话 / 新 Agent 看的快速交接文档。继续开发本项目时，请先阅读本文件，再阅读 `README.md`、`CHANGELOG.md`、`ROADMAP.md` 和 `docs/plans/`。
>
> 更新时间：2026-04-25 00:18 CST

## 1. 项目定位

`庄家雷达 / Banker Radar` 是一个加密市场异动监控与解释系统，目标是发现并追踪：

- 收筹池 / 横盘蓄势；
- 暗流吸筹；
- 空头燃料 / 轧空风险；
- Smart Money 链上异动；
- 链上链下共振；
- 诱多、派发、砸盘等高风险结构；
- 信号出现后的 15m / 1h / 4h / 24h 表现。

当前项目**不做自动交易**，只做市场异动监控、解释、Telegram 推送和后续统计复盘。所有输出都应保留“非投资建议”口径。

## 2. 仓库与部署位置

- 本机项目路径：`/root/banker-radar`
- GitHub 仓库：`https://github.com/newplayman/radar`
- Git remote：`git@github.com:newplayman/radar.git`
- 当前主要分支：`main`
- 最近提交：
  - `40a10f7 fix: backfill tracking entry price for exchange symbols`
  - `7c16dcc fix: make postgres the production storage default`
  - `81498cd feat: add signal tracking backtesting v0.4`
- GitHub push 使用 SSH key：`/root/.ssh/github_polymarket`
- SSH key 指纹：`SHA256:T/B2087WgJjqmTUi+Y2+EP09oJsZOB5KlsvFDaA3Hxw`

推送时建议显式指定 key：

```bash
GIT_SSH_COMMAND='ssh -i /root/.ssh/github_polymarket -o IdentitiesOnly=yes' git push origin main
```

## 3. 敏感信息规则

任何新对话、新文档、日志摘要里都不要输出真实敏感信息。

必须视为敏感并写作 `[REDACTED]`：

- Telegram bot token；
- PostgreSQL / `DATABASE_URL`；
- sudo/root 密码；
- API key；
- 私钥；
- SSH private key 内容；
- 数据库连接串完整明文。

本地敏感配置文件：

- `/root/banker-radar/.env`

`.env` 不应进入 git。

## 4. 当前版本能力总览

### v0.1 — 市场雷达 MVP

已完成：

- 模块化项目结构；
- Binance USDT 永续公共数据采集；
- OKX OI-change 公共数据接入；
- 收筹池检测：长期横盘、窄区间、低成交、低斜率；
- 三类基础信号：
  - `暗流吸筹`；
  - `空头燃料`；
  - `综合异动`；
- Telegram 风格报告 formatter；
- 初版单元测试。

### v0.2 — Telegram 产品化

已完成：

- `banker-radar telegram-send`：手动扫描并推送；
- `banker-radar telegram-schedule`：定时扫描并推送；
- `banker-radar telegram-bot`：长轮询处理 Telegram @提及查询；
- `.env` 自动加载；
- 群组内默认只响应 @提及，避免干扰普通聊天；
- 独立 Telegram bot 已部署。

Telegram 当前信息：

- Bot：`@zhuangjialeida_bot`
- Chat ID：`-1003903984676`
- Token：`[REDACTED]`

### v0.3 — Smart Money / GMGN / PostgreSQL

已完成：

- Binance Web3 Smart Money collector；
- GMGN CLI fallback；
- Provider fallback + cooldown + 自恢复；
- Token Audit 高风险过滤；
- `🧠 链上聪明钱榜`；
- `🧬 链上链下共振榜`；
- `--no-smart-money` 降级开关；
- PostgreSQL JSONB 存储。

设计原则：链上模块不可用时，必须自动降级为 OKX/Binance 合约雷达，不能影响核心 Telegram 播报。

### v0.4 — 信号追踪与回测复盘

已完成：

- `banker-radar track-signals`；
- `banker-radar backtest-report`；
- `banker-radar telegram-review`；
- 追踪窗口：15m / 1h / 4h / 24h；
- 指标：`return_pct`、`max_runup_pct`、`max_drawdown_pct`、`success`、`is_outlier`；
- 方向推断：
  - `空头燃料`、`暗流吸筹`、`链上聪明钱`、`链上链下共振` → `long`；
  - `空头压制` → `short`；
  - `综合异动` → `neutral`；
- PostgreSQL tracking 表：`signal_tracking`、`provider_cooldowns`、`review_sends`；
- PostgreSQL 并发/幂等设计：`FOR UPDATE SKIP LOCKED`、`ON CONFLICT DO NOTHING`；
- systemd 模板与生产 timer；
- Telegram 每日复盘幂等发送。

复盘口径必须保留：

```text
非投资建议；复盘仅为信号后价格表现统计，未计滑点/手续费/真实成交可得性。
```

## 5. 数据库状态与原则

生产数据库：**PostgreSQL only**。

- `configs/radar.yaml` 中 `storage.backend: postgres`；
- `.env` 中提供 `DATABASE_URL=[REDACTED]`；
- systemd unit 不应带 `--db data/radar.db`；
- SQLite 只允许用于单元测试或显式本地临时验证，不能作为生产 fallback。

截至 2026-04-25 00:18 CST，生产 PostgreSQL 表统计：

```text
radar_signals=102
signal_tracking=408
review_sends=0
provider_cooldowns=0
tracking_status completed=139
tracking_status failed_permanent=51
tracking_status failed_retryable=23
tracking_status pending=195
```

失败状态里常见原因是小众链上 token 无法用 CEX K 线回填价格。后续可考虑接 GMGN/token price provider，或把无法追踪的纯链上 token 更早标记为 `failed_permanent`。

## 6. 当前 systemd 生产服务

当前已经启用：

```text
banker-radar-telegram.timer
banker-radar-telegram-bot.service
banker-radar-tracking.timer
banker-radar-daily-review.timer
```

截至 2026-04-25 00:18 CST：

```text
banker-radar-telegram.timer     active, hourly, next around 01:00 CST
banker-radar-tracking.timer     active, every ~15 minutes
banker-radar-daily-review.timer active, next around 09:05 CST
banker-radar-telegram-bot.service active (running)
```

关键 ExecStart 口径：

```text
banker-radar telegram-schedule --once --config /root/banker-radar/configs/radar.yaml
banker-radar telegram-bot --config /root/banker-radar/configs/radar.yaml
banker-radar track-signals --config /root/banker-radar/configs/radar.yaml
banker-radar telegram-review --period yesterday --config /root/banker-radar/configs/radar.yaml
```

所有生产 unit 都应通过 `/root/banker-radar/.env` 读取 `DATABASE_URL` 和 Telegram 配置。

常用检查命令：

```bash
systemctl list-timers 'banker-radar-*' --no-pager --all
systemctl status banker-radar-telegram.timer banker-radar-tracking.timer banker-radar-daily-review.timer banker-radar-telegram-bot.service --no-pager -l
journalctl -u banker-radar-tracking.service -n 80 --no-pager
journalctl -u banker-radar-daily-review.service -n 80 --no-pager
journalctl -u banker-radar-telegram.service -n 80 --no-pager
journalctl -u banker-radar-telegram-bot.service -n 80 --no-pager
```

## 7. 当前是否调用 LLM / 模型

当前庄家雷达项目**不调用 GPT-5.5，也不调用任何 LLM API**。

当前架构是：

```text
OKX / Binance / GMGN 市场数据
+ 规则引擎
+ 打分函数
+ PostgreSQL
+ Telegram 模板化播报
```

因此 Hermes 切换模型到 MiniMax CN 不会影响庄家雷达成本。庄家雷达目前没有 LLM 成本。

未来如果加 LLM，应设计为可选增强，默认关闭，例如：

```yaml
llm_explanation:
  enabled: false
  provider: minimax-cn
  model: ""
  max_calls_per_day: 20
  only_for_score_above: 85
```

建议只在强信号上调用 LLM 做解释，不要让 LLM 成为核心扫描链路依赖。

## 8. 常用命令

开发/测试：

```bash
cd /root/banker-radar
python3 -m pytest -q
```

扫描：

```bash
banker-radar scan --config configs/radar.yaml
banker-radar scan --no-smart-money --config configs/radar.yaml
```

Telegram：

```bash
banker-radar telegram-send --config configs/radar.yaml
banker-radar telegram-send --dry-run --config configs/radar.yaml
banker-radar telegram-schedule --once --config configs/radar.yaml
banker-radar telegram-bot --config configs/radar.yaml
```

追踪/复盘：

```bash
banker-radar track-signals --config configs/radar.yaml --limit 50
banker-radar backtest-report --config configs/radar.yaml --period today
banker-radar telegram-review --config configs/radar.yaml --period yesterday --dry-run
banker-radar telegram-review --config configs/radar.yaml --period yesterday
```

生产默认使用 PostgreSQL，不要在生产命令里加 `--db data/radar.db`。

## 9. 重要源码位置

```text
configs/radar.yaml
src/banker_radar/cli.py
src/banker_radar/collectors/binance_futures.py
src/banker_radar/collectors/okx_market.py
src/banker_radar/collectors/binance_web3.py
src/banker_radar/collectors/gmgn.py
src/banker_radar/collectors/chain.py
src/banker_radar/collectors/price_observer.py
src/banker_radar/engines/accumulation.py
src/banker_radar/signals/scoring.py
src/banker_radar/signals/smart_money.py
src/banker_radar/signals/resonance.py
src/banker_radar/tracking/direction.py
src/banker_radar/tracking/performance.py
src/banker_radar/tracking/service.py
src/banker_radar/storage/postgres.py
src/banker_radar/storage/sqlite.py
src/banker_radar/storage/__init__.py
src/banker_radar/alerts/formatter.py
src/banker_radar/alerts/telegram.py
src/banker_radar/telegram/bot.py
src/banker_radar/utils/rate_limit.py
deploy/systemd/
tests/
```

## 10. 下一步建议：v0.5

推荐优先方向：**单币深度分析 + 风险榜增强**。

候选功能：

1. Telegram 单币深度分析：
   - `@zhuangjialeida_bot 分析 BTC`；
   - 输出价格、OI、资金费率、成交量、近期信号、追踪表现、风险解释。
2. OKX/Binance orderbook 与 trades：
   - 盘口深度；
   - 买卖盘失衡；
   - 主动成交；
   - 大单扫单。
3. 风险/诱多榜：
   - OI 增 + 高位拉升 + 极端正费率；
   - Smart Money exitRate 高；
   - CEX 拉盘但链上出货；
   - 价格已大幅偏离触发价。
4. 纯链上 token 价格追踪优化：
   - GMGN/token price provider；
   - 无 CEX K 线时不反复 retry；
   - 将不可追踪原因写入 metadata。
5. 运行监控：
   - systemd health check；
   - PostgreSQL 表增长和失败率；
   - Telegram 推送失败告警。

## 11. 新对话建议开场

如果在 OpenWebUI 新开对话，建议第一条这样写：

```text
我们继续开发“庄家雷达”项目。项目在 /root/banker-radar，GitHub 仓库是 https://github.com/newplayman/radar。

请先读取 docs/PROJECT_CONTEXT.md、README.md、CHANGELOG.md、ROADMAP.md 和 docs/plans/，再继续规划/开发下一版。注意：生产只用 PostgreSQL；SQLite 仅测试显式使用；项目当前不调用 LLM；systemd 已启用 telegram、telegram-bot、tracking、daily-review。
```
