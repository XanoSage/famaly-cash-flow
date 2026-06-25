from fastapi.testclient import TestClient

from app.api.routes import telegram
from app.main import app
from app.telegram_bot.dispatcher import BotReply, START_TEXT


def reset_telegram_settings(monkeypatch) -> None:
    monkeypatch.setattr(telegram.settings, "telegram_bot_token", None)
    monkeypatch.setattr(telegram.settings, "telegram_webhook_secret_token", None)
    monkeypatch.setattr(telegram.settings, "telegram_default_family_id", None)


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


def test_telegram_webhook_sends_summary_reply(monkeypatch) -> None:
    reset_telegram_settings(monkeypatch)
    sent = {}

    def fake_build_summary_text(db, family_id_value: str | None) -> str:
        sent["family_id_value"] = family_id_value
        return "Summary text"

    def fake_send_bot_replies(bot_token: str | None, replies: list[BotReply]) -> int:
        sent["bot_token"] = bot_token
        sent["replies"] = replies
        return len(replies)

    monkeypatch.setattr(telegram.settings, "telegram_bot_token", "token-123")
    monkeypatch.setattr(telegram.settings, "telegram_default_family_id", "family-123")
    monkeypatch.setattr(telegram, "build_summary_text", fake_build_summary_text)
    monkeypatch.setattr(telegram, "send_bot_replies", fake_send_bot_replies)
    client = TestClient(app)

    response = client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 42, "type": "private"},
                "text": "/summary",
            },
        },
    )

    assert response.status_code == 200
    assert sent["bot_token"] == "token-123"
    assert sent["family_id_value"] == "family-123"
    assert sent["replies"] == [BotReply(chat_id=42, text="Summary text")]


def test_telegram_webhook_sends_review_reply(monkeypatch) -> None:
    reset_telegram_settings(monkeypatch)
    sent = {}

    def fake_build_review_text(db, family_id_value: str | None) -> str:
        sent["family_id_value"] = family_id_value
        return "Review text"

    def fake_send_bot_replies(bot_token: str | None, replies: list[BotReply]) -> int:
        sent["bot_token"] = bot_token
        sent["replies"] = replies
        return len(replies)

    monkeypatch.setattr(telegram.settings, "telegram_bot_token", "token-123")
    monkeypatch.setattr(telegram.settings, "telegram_default_family_id", "family-123")
    monkeypatch.setattr(telegram, "build_review_text", fake_build_review_text)
    monkeypatch.setattr(telegram, "send_bot_replies", fake_send_bot_replies)
    client = TestClient(app)

    response = client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 42, "type": "private"},
                "text": "/review",
            },
        },
    )

    assert response.status_code == 200
    assert sent["bot_token"] == "token-123"
    assert sent["family_id_value"] == "family-123"
    assert sent["replies"] == [BotReply(chat_id=42, text="Review text")]
