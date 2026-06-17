from fastapi.testclient import TestClient

from app.api.routes import telegram
from app.main import app


def test_telegram_webhook_accepts_update_without_secret() -> None:
    client = TestClient(app)

    response = client.post("/api/v1/telegram/webhook", json={"update_id": 1})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_telegram_webhook_rejects_invalid_secret(monkeypatch) -> None:
    monkeypatch.setattr(telegram.settings, "telegram_webhook_secret_token", "expected-secret")
    client = TestClient(app)

    response = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        json={"update_id": 1},
    )

    assert response.status_code == 401


def test_telegram_webhook_accepts_valid_secret(monkeypatch) -> None:
    monkeypatch.setattr(telegram.settings, "telegram_webhook_secret_token", "expected-secret")
    client = TestClient(app)

    response = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
        json={"update_id": 1},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
