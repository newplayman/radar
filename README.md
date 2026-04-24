# 庄家雷达 / Banker Radar v0.1

MVP 目标：把 `accumulation-radar` 的“收筹池 + 暗流信号 + 轧空榜”思路模块化，并接入当前机器上的 Binance 公共合约数据与 OKX CLI 公共市场数据。

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
- 单元测试：9 个。

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
```

## 下一步 v0.2

1. Telegram 定时推送接入当前 Hermes gateway/bot。
2. Binance Web3 Smart Money 榜接入。
3. 信号落库后的 15m/1h/4h/24h 追踪回测。
4. OKX/Binance 同币种共振合并，避免重复并提升可信度。
5. 单币交互：`@ctb007_bot 分析 SAGA`。
