import json
from urllib.error import URLError

import pytest

from app.telegram_bot import client
from app.telegram_bot.client import TelegramApiError, send_bot_replies, send_message
from app.telegram_bot.dispatcher import BotReply


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def test_send_bot_replies_skips_without_token(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(client, "send_message", lambda *args, **kwargs: calls.append((args, kwargs)))

    sent_count = send_bot_replies(None, [BotReply(chat_id=42, text="hello")])

    assert sent_count == 0
    assert calls == []


def test_send_message_posts_to_telegram_api(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["content_type"] = request.headers["Content-type"]
        return FakeResponse(b'{"ok": true, "result": {"message_id": 10}}')

    monkeypatch.setattr(client, "urlopen", fake_urlopen)

    response = send_message("token-123", chat_id=42, text="hello")

    assert response["ok"] is True
    assert captured == {
        "url": "https://api.telegram.org/bottoken-123/sendMessage",
        "timeout": 10.0,
        "payload": {"chat_id": 42, "text": "hello"},
        "content_type": "application/json",
    }


def test_send_message_raises_on_network_error(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise URLError("network down")

    monkeypatch.setattr(client, "urlopen", fake_urlopen)

    with pytest.raises(TelegramApiError):
        send_message("token-123", chat_id=42, text="hello")
