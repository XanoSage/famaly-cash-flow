import json
from urllib.error import URLError

import pytest

from app.telegram_bot import client
from app.telegram_bot.client import TelegramApiError, answer_callback_query, send_bot_replies, send_message
from app.telegram_bot.dispatcher import BotCallbackAnswer, BotReply


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


def test_send_message_posts_reply_markup(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(b'{"ok": true, "result": {"message_id": 10}}')

    monkeypatch.setattr(client, "urlopen", fake_urlopen)

    send_message(
        "token-123",
        chat_id=42,
        text="hello",
        reply_markup={"inline_keyboard": [[{"text": "Done", "callback_data": "review_done:1"}]]},
    )

    assert captured["payload"] == {
        "chat_id": 42,
        "text": "hello",
        "reply_markup": {"inline_keyboard": [[{"text": "Done", "callback_data": "review_done:1"}]]},
    }


def test_answer_callback_query_posts_to_telegram_api(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(b'{"ok": true, "result": true}')

    monkeypatch.setattr(client, "urlopen", fake_urlopen)

    response = answer_callback_query("token-123", callback_query_id="callback-1", text="Done")

    assert response["ok"] is True
    assert captured == {
        "url": "https://api.telegram.org/bottoken-123/answerCallbackQuery",
        "payload": {"callback_query_id": "callback-1", "text": "Done"},
    }


def test_send_bot_replies_sends_callback_answers(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(client, "send_message", lambda *args, **kwargs: calls.append(("message", args, kwargs)))
    monkeypatch.setattr(
        client,
        "answer_callback_query",
        lambda *args, **kwargs: calls.append(("callback", args, kwargs)),
    )

    sent_count = send_bot_replies(
        "token-123",
        [
            BotCallbackAnswer(callback_query_id="callback-1", text="Done"),
            BotReply(chat_id=42, text="Visible done"),
        ],
    )

    assert sent_count == 2
    assert calls[0][0] == "callback"
    assert calls[1][0] == "message"


def test_send_message_raises_on_network_error(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise URLError("network down")

    monkeypatch.setattr(client, "urlopen", fake_urlopen)

    with pytest.raises(TelegramApiError):
        send_message("token-123", chat_id=42, text="hello")
