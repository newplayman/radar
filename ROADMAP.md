# 庄家雷达 Roadmap

> 目标：把庄家雷达从“可跑的异动扫描器”逐步迭代成“多市场主力异动情报系统”。
>
> 项目只做市场异动监控和解释，不构成投资建议，也不内置自动交易。

## 当前状态

- 当前版本：v0.2.0
- 核心能力：Binance/OKX 公共合约数据扫描、收筹/暗流/轧空/综合异动评分、SQLite 落库、Telegram 定时播报和 @提及查询。
- 部署形态：CLI + systemd timer/service。

## Milestone 0 — 项目启动与 v0.1 MVP（已完成）

目标：验证“收筹池 + OI 异动 + 资金费率”的基础雷达闭环。

已完成：

- 模块化项目骨架。
- Binance USDT 永续公共数据采集。
- OKX CLI 公共市场 OI 榜接入。
- 收筹池检测：横盘天数、区间幅度、均量、斜率。
- 三类基础信号：暗流吸筹、空头燃料、综合异动。
- SQLite 落库。
- Telegram 风格报告 formatter。
- 单元测试覆盖核心评分/格式化/存储逻辑。

## Milestone 1 — v0.2 Telegram 产品化（已完成）

目标：让雷达可以在 Telegram 频道/群组里持续使用。

已完成：

- `telegram-send`：手动扫描并推送。
- `telegram-schedule`：定时扫描并推送，适合 systemd/cron。
- `telegram-bot`：长轮询处理 @提及查询。
- `.env` 自动加载，避免把 token 写入仓库。
- 群组只响应 @提及，避免打扰普通聊天。
- 独立 Telegram 机器人部署验证。

## Milestone 2 — v0.3 Smart Money 与共振信号

目标：接入 Binance Web3 / 链上聪明钱数据，形成“链上 + 合约”共振判断。

计划：

- Smart Money Buy/Sell 数据采集。
- Whale Buy/Sell、exitRate、maxGain、token tag 解析。
- Token Audit 风险过滤。
- Meme Rush / 市场热度作为预热信号。
- 新增榜单：`🧠 链上聪明钱榜`、`🧬 链上链下共振榜`。
- 合并同一标的在 OKX/Binance/链上的多源信号，减少重复推送。

## Milestone 3 — v0.4 信号追踪与回测

目标：验证信号是否具有统计优势，避免“玄学雷达”。

计划：

- 每条信号落库时记录 entry price、score、signal_type、features。
- 自动追踪 15m / 1h / 4h / 24h 后价格表现。
- 统计 max_runup、max_drawdown、胜率、平均收益、盈亏比。
- 每日自动生成“昨日信号复盘”。
- 为不同信号类型单独统计表现：暗流吸筹、空头燃料、综合异动、链上共振。

## Milestone 4 — v0.5 单币深度分析

目标：让用户可以通过 Telegram 查询某个币的多维解释。

计划：

- `分析 SYMBOL` 输出价格、OI、资金费率、成交量、市值、风险解释。
- OKX orderbook / trades 接入：盘口深度、买卖盘失衡、大额成交。
- 支持观察位、失效条件和风险提示。
- 支持 watchlist：`盯盘 BTC ETH SOL`。

## Milestone 5 — v1.0 稳定版

目标：形成可长期运行的生产级雷达服务。

计划：

- 配置化策略参数和阈值。
- 推送冷却/去重/分级告警。
- Prometheus/日志监控与异常告警。
- 可选迁移到 PostgreSQL/TimescaleDB。
- Docker/systemd 一键部署文档。
- 完整测试矩阵和 CI。

## 非目标

- 不做自动下单。
- 不承诺盈利或确定性判断。
- 不在仓库中保存任何 API token、Telegram token、私钥或数据库快照。
