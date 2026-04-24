from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from banker_radar.models import RadarSignal


def _section_title(kind: str) -> str:
    if kind == "链上链下共振":
        return "🧬 链上链下共振榜"
    if kind == "链上聪明钱":
        return "🧠 链上聪明钱榜"
    if kind == "暗流吸筹":
        return "🎯 暗流/埋伏榜"
    if kind == "空头燃料":
        return "🔥 轧空/追多榜"
    return "📊 综合异动榜"


def format_report(signals: list[RadarSignal], *, title: str = "庄家雷达 v0.1") -> str:
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M CST")
    lines = [f"🏦 {title}", f"⏰ {now}", ""]
    if not signals:
        lines += ["本轮未发现超过阈值的异动。", "", "⚠️ 非投资建议，仅为市场异动监控。"]
        return "\n".join(lines)

    groups: dict[str, list[RadarSignal]] = defaultdict(list)
    for s in sorted(signals, key=lambda x: x.score, reverse=True):
        groups[_section_title(s.kind)].append(s)

    order = ["🧬 链上链下共振榜", "🧠 链上聪明钱榜", "🔥 轧空/追多榜", "🎯 暗流/埋伏榜", "📊 综合异动榜"]
    for section in order:
        rows = groups.get(section, [])
        if not rows:
            continue
        lines.append(section)
        for i, s in enumerate(rows[:5], 1):
            lines.append(f"{i}. {s.symbol}｜{s.score}分｜{s.kind}｜风险:{s.risk}")
            lines.append(f"   {s.reason}｜源:{s.source}")
        lines.append("")

    lines.append("⚠️ 非投资建议，仅为市场异动监控。")
    return "\n".join(lines)



def format_backtest_report(summaries, *, title: str = "庄家雷达 v0.4 复盘", period_label: str = "昨日") -> str:
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M CST")
    lines = [f"📈 {title}", f"周期：{period_label}", f"⏰ {now}", ""]
    if not summaries:
        lines += ["暂无已完成追踪样本。", "", "⚠️ 非投资建议；复盘仅为信号后价格表现统计，未计滑点/手续费/真实成交可得性。"]
        return "\n".join(lines)
    for s in summaries[:12]:
        warn = f"｜{s.sample_warning}" if s.sample_warning else ""
        outlier = f"｜异常样本:{s.outlier_count}" if getattr(s, "outlier_count", 0) else ""
        lines.append(f"{s.kind} {s.window_minutes}m｜样本:{s.total}｜方向样本:{s.directional_total if s.directional_total is not None else s.total}{warn}{outlier}")
        lines.append(f"胜率:{s.win_rate_pct:.1f}%｜平均收益:{s.avg_return_pct:+.2f}%｜平均回撤:{s.avg_max_drawdown_pct:+.2f}%｜平均最大顺势:{s.avg_max_runup_pct:+.2f}%")
    lines += ["", "⚠️ 非投资建议；复盘仅为信号后价格表现统计，未计滑点/手续费/真实成交可得性。"]
    return "\n".join(lines)
