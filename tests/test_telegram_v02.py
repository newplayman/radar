from banker_radar.telegram.bot import TelegramRadarBot, parse_command
from banker_radar.alerts.telegram import TelegramClient


class FakeHttp:
    def __init__(self):
        self.calls = []
        self.responses = []

    def post_json(self, url, payload, timeout=15):
        self.calls.append((url, payload, timeout))
        return self.responses.pop(0) if self.responses else {"ok": True, "result": {"message_id": 1}}

    def get_json(self, url, params=None, timeout=35):
        self.calls.append((url, params or {}, timeout))
        return self.responses.pop(0)


def test_telegram_client_sends_markdown_safe_message():
    http = FakeHttp()
    client = TelegramClient(token="TOKEN", chat_id="-1001", http=http)

    result = client.send_message("🏦 test")

    assert result["ok"] is True
    url, payload, timeout = http.calls[0]
    assert url == "https://api.telegram.org/botTOKEN/sendMessage"
    assert payload["chat_id"] == "-1001"
    assert payload["text"] == "🏦 test"
    assert payload["disable_web_page_preview"] is True


def test_parse_command_requires_mention_in_group_and_extracts_analyze_symbol():
    assert parse_command("分析 APE", bot_username="ctb007_bot", require_mention=True, chat_type="private") == ("analyze", "APEUSDT")
    assert parse_command("@ctb007_bot 分析 APE", bot_username="ctb007_bot", require_mention=True, chat_type="supergroup") == ("analyze", "APEUSDT")
    assert parse_command("分析 APE", bot_username="ctb007_bot", require_mention=True, chat_type="supergroup") is None
    assert parse_command("@other_bot 庄家雷达", bot_username="ctb007_bot", require_mention=True, chat_type="supergroup") is None


def test_bot_replies_to_scan_and_analyze_updates():
    replies = []

    def scan_fn(symbols=None):
        return "REPORT " + (",".join(symbols or []) if symbols else "ALL")

    bot = TelegramRadarBot(
        bot_username="ctb007_bot",
        require_mention=True,
        scan_fn=scan_fn,
        send_fn=lambda chat_id, text: replies.append((chat_id, text)),
    )
    updates = [
        {"update_id": 10, "message": {"chat": {"id": -1001, "type": "supergroup"}, "text": "普通聊天"}},
        {"update_id": 11, "message": {"chat": {"id": -1001, "type": "supergroup"}, "text": "@ctb007_bot 庄家雷达"}},
        {"update_id": 12, "message": {"chat": {"id": -1001, "type": "supergroup"}, "text": "@ctb007_bot 分析 APE"}},
    ]

    next_offset = bot.handle_updates(updates)

    assert next_offset == 13
    assert replies == [(-1001, "REPORT ALL"), (-1001, "REPORT APEUSDT")]
