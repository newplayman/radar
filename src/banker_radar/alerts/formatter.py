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
