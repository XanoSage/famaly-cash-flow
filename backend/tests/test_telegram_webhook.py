from fastapi.testclient import TestClient

from app.api.routes import telegram
from app.main import app
from app.telegram_bot.dispatcher import BotReply, START_TEXT


def reset_telegram_settings(monkeypatch) -> None:
    monkeypatch.setattr(telegram.settings, "telegram_bot_token", None)
    monkeypatch.setattr(telegram.settings, "telegram_webhook_secret_token", None)


def test_telegram_webhook_accepts_update_without_secret(monkeypatch) -> None:
    reset_telegram_settings(monkeypatch)
    client = TestClient(app)

    response = client.post("/api/v1/telegram/webhook", json={"update_id": 1})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_telegram_webhook_rejects_invalid_secret(monkeypatch) -> None:
    reset_telegram_settings(monkeypatch)
    monkeypatch.setattr(telegram.settings, "telegram_webhook_secret_token", "expected-secret")
    client = TestClient(app)

    response = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        json={"update_id": 1},
    )

    assert response.status_code == 401


def test_telegram_webhook_accepts_valid_secret(monkeypatch) -> None:
    reset_telegram_settings(monkeypatch)
    monkeypatch.setattr(telegram.settings, "telegram_webhook_secret_token", "expected-secret")
    client = TestClient(app)

    response = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
        json={"update_id": 1},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_telegram_webhook_sends_dispatcher_replies(monkeypatch) -> None:
    reset_telegram_settings(monkeypatch)
    sent = {}

    def fake_send_bot_replies(bot_token: str | None, replies: list[BotReply]) -> int:
        sent["bot_token"] = bot_token
        sent["replies"] = replies
        return len(replies)

    monkeypatch.setattr(telegram.settings, "telegram_bot_token", "token-123")
    monkeypatch.setattr(telegram, "send_bot_replies", fake_send_bot_replies)
    client = TestClient(app)

    response = client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 42, "type": "private"},
                "text": "/start",
            },
        },
    )

    assert response.status_code == 200
    assert sent["bot_token"] == "token-123"
    assert sent["replies"] == [BotReply(chat_id=42, text=START_TEXT)]
