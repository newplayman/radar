from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

Command = tuple[str, str | None]


def normalize_symbol(raw: str) -> str:
    token = raw.strip().upper().replace("-", "").replace("/", "")
    if not token:
        return token
    if not token.endswith("USDT"):
        token = f"{token}USDT"
    return token


def parse_command(text: str, *, bot_username: str, require_mention: bool, chat_type: str) -> Command | None:
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    is_group = chat_type in {"group", "supergroup"}
    mention_pattern = re.compile(rf"@{re.escape(bot_username)}\b", re.IGNORECASE)
    mentions_me = bool(mention_pattern.search(cleaned))
    mentions_other = bool(re.search(r"@[A-Za-z0-9_]+", cleaned)) and not mentions_me

    if is_group and require_mention and not mentions_me:
        return None
    if mentions_other and not mentions_me:
        return None
    cleaned = mention_pattern.sub("", cleaned).strip()

    if cleaned in {"庄家雷达", "今日异动", "合约雷达", "雷达", "/radar", "/scan", "scan"}:
        return ("scan", None)
    if cleaned in {"帮助", "help", "/help", "?"}:
        return ("help", None)

    m = re.match(r"^(?:分析|analyze|/analyze)\s+([A-Za-z0-9_\-/]+)$", cleaned, re.IGNORECASE)
    if m:
        return ("analyze", normalize_symbol(m.group(1)))
    return None


HELP_TEXT = """🏦 庄家雷达 v0.2

可用命令：
- @ctb007_bot 庄家雷达
- @ctb007_bot 今日异动
- @ctb007_bot 分析 APE

群组内默认只响应 @提及，避免打扰普通聊天。"""


@dataclass
class TelegramRadarBot:
    bot_username: str
    require_mention: bool
    scan_fn: Callable[[list[str] | None], str]
    send_fn: Callable[[int | str, str], Any]

    def handle_updates(self, updates: list[dict[str, Any]]) -> int | None:
        next_offset: int | None = None
        for update in updates:
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                next_offset = max(next_offset or 0, update_id + 1)

            message = update.get("message") or {}
            text = message.get("text") or ""
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            chat_type = chat.get("type", "private")
            if chat_id is None:
                continue

            parsed = parse_command(text, bot_username=self.bot_username, require_mention=self.require_mention, chat_type=chat_type)
            if parsed is None:
                continue
            command, arg = parsed
            if command == "help":
                reply = HELP_TEXT
            elif command == "analyze" and arg:
                reply = self.scan_fn([arg])
            else:
                reply = self.scan_fn(None)
            self.send_fn(chat_id, reply)
        return next_offset

    def poll_forever(self, get_updates_fn: Callable[[int | None], list[dict[str, Any]]], *, sleep_seconds: float = 1.0) -> None:
        offset: int | None = None
        while True:
            updates = get_updates_fn(offset)
            next_offset = self.handle_updates(updates)
            if next_offset is not None:
                offset = next_offset
            time.sleep(sleep_seconds)
