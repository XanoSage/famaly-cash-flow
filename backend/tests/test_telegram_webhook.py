from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.routes import telegram
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.telegram_bot.context import PRIVATE_CHAT_ONLY_TEXT, START_TEXT, UNLINKED_TELEGRAM_TEXT
from app.telegram_bot.dispatcher import BotReply


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_telegram_webhook_accepts_updates_when_no_secret_is_configured(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(telegram.settings, "telegram_webhook_secret_token", None)

    response = client.post("/api/v1/telegram/webhook", json={"update_id": 1})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_telegram_webhook_rejects_missing_or_invalid_secret(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(telegram.settings, "telegram_webhook_secret_token", "expected-secret")

    missing = client.post("/api/v1/telegram/webhook", json={"update_id": 1})
    invalid = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        json={"update_id": 1},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401


def test_telegram_webhook_accepts_valid_secret_and_dispatches_safe_start_reply(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: dict[str, object] = {}
    monkeypatch.setattr(telegram.settings, "telegram_webhook_secret_token", "expected-secret")
    monkeypatch.setattr(telegram.settings, "telegram_bot_token", "test-bot-token")
    monkeypatch.setattr(
        telegram,
        "send_bot_replies",
        lambda token, replies: sent.update(token=token, replies=replies) or len(replies),
    )

    response = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
        json={
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 42, "type": "private"},
                "from": {"id": 77},
                "text": "/start",
            },
        },
    )

    assert response.status_code == 200
    assert sent["token"] == "test-bot-token"
    assert sent["replies"] == [BotReply(chat_id=42, text=START_TEXT)]


@pytest.mark.parametrize(
    ("chat_type", "expected"),
    [("private", UNLINKED_TELEGRAM_TEXT), ("group", PRIVATE_CHAT_ONLY_TEXT)],
)
def test_unlinked_telegram_user_never_gets_summary_data(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    chat_type: str,
    expected: str,
) -> None:
    sent: list[BotReply] = []
    monkeypatch.setattr(
        telegram, "send_bot_replies", lambda _token, replies: sent.extend(replies) or 1
    )

    response = client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 2,
            "message": {
                "message_id": 11,
                "chat": {"id": 42, "type": chat_type},
                "from": {"id": 77},
                "text": "/summary",
            },
        },
    )

    assert response.status_code == 200
    assert sent == [BotReply(chat_id=42, text=expected)]
    assert all("Доходы:" not in reply.text for reply in sent)
