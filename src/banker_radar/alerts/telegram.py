from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


class HttpTransport(Protocol):
    def post_json(self, url: str, payload: dict[str, Any], timeout: int = 15) -> dict[str, Any]: ...
    def get_json(self, url: str, params: dict[str, Any] | None = None, timeout: int = 35) -> dict[str, Any]: ...


class UrllibHttpTransport:
    def post_json(self, url: str, payload: dict[str, Any], timeout: int = 15) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - user-configured Telegram API URL
            return json.loads(resp.read().decode("utf-8"))

    def get_json(self, url: str, params: dict[str, Any] | None = None, timeout: int = 35) -> dict[str, Any]:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - user-configured Telegram API URL
            return json.loads(resp.read().decode("utf-8"))


@dataclass
class TelegramClient:
    token: str
    chat_id: str | int | None = None
    http: HttpTransport | None = None
    api_base: str = "https://api.telegram.org"

    def __post_init__(self) -> None:
        if self.http is None:
            self.http = UrllibHttpTransport()

    @property
    def base_url(self) -> str:
        return f"{self.api_base}/bot{self.token}"

    def send_message(self, text: str, chat_id: str | int | None = None) -> dict[str, Any]:
        target = chat_id if chat_id is not None else self.chat_id
        if target is None:
            raise ValueError("telegram chat_id is required")
        payload = {
            "chat_id": str(target),
            "text": text,
            "disable_web_page_preview": True,
        }
        assert self.http is not None
        result = self.http.post_json(f"{self.base_url}/sendMessage", payload, timeout=15)
        if not result.get("ok"):
            raise RuntimeError(f"Telegram sendMessage failed: {result}")
        return result

    def get_updates(self, *, offset: int | None = None, timeout: int = 30) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": timeout, "allowed_updates": json.dumps(["message"])}
        if offset is not None:
            params["offset"] = offset
        assert self.http is not None
        result = self.http.get_json(f"{self.base_url}/getUpdates", params=params, timeout=timeout + 5)
        if not result.get("ok"):
            raise RuntimeError(f"Telegram getUpdates failed: {result}")
        return list(result.get("result", []))
