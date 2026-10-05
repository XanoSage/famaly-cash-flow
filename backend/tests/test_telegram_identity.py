from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.routes import telegram
from app.auth.dependencies import get_current_user
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.account import Account
from app.models.category import Category
from app.models.family import Family
from app.models.telegram_identity import TelegramIdentity, TelegramLinkToken
from app.models.transaction import Transaction
from app.models.user import User
from app.services.account_preferences import AccountPreferenceService, DefaultAccountError
from app.services.telegram_linking import (
    TELEGRAM_LINK_TOKEN_LIFETIME,
    consume_telegram_link_token,
    create_telegram_link,
    hash_telegram_link_token,
    unlink_telegram_identity,
)
from app.telegram_bot.accounts import ACCOUNT_NOT_FOUND_TEXT, ACCOUNT_SELECTED_TEXT
from app.telegram_bot.context import resolve_telegram_context
from app.telegram_bot.dispatcher import BotReply
from app.telegram_bot.review import REVIEW_TRANSACTION_NOT_FOUND_TEXT


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


def test_link_api_requires_auth_and_persists_only_token_hash(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert client.post("/api/v1/telegram/link-token").status_code == 401
    _, user, _ = _seed_user(db_session)
    _as_user(user)
    monkeypatch.setattr(telegram.settings, "telegram_bot_username", "FamilyCashFlowBot")

    response = client.post("/api/v1/telegram/link-token")

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    body = response.json()
    assert body["telegram_url"] == f"https://t.me/FamilyCashFlowBot?start={body['token']}"
    assert datetime.fromisoformat(body["expires_at"]) > datetime.now(UTC)
    token_row = db_session.scalar(select(TelegramLinkToken))
    assert token_row is not None
    assert token_row.token_hash == hash_telegram_link_token(body["token"])
    assert token_row.token_hash != body["token"]
    assert client.get("/api/v1/telegram/link-status").json() == {
        "is_linked": False,
        "username": None,
        "first_name": None,
        "linked_at": None,
    }


def test_start_token_links_from_numeric_sender_in_private_chat_and_rejects_replay(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family, user, _ = _seed_user(db_session)
    link = create_telegram_link(db_session, user_id=user.id, bot_username=None)
    sent: list[BotReply] = []
    monkeypatch.setattr(
        telegram, "send_bot_replies", lambda _token, replies: sent.extend(replies) or 1
    )
    monkeypatch.setattr(telegram.settings, "telegram_webhook_secret_token", "hook-secret")
    headers = {"X-Telegram-Bot-Api-Secret-Token": "hook-secret"}

    group_response = client.post(
        "/api/v1/telegram/webhook",
        headers=headers,
        json=_message_update(
            "/start " + link.token, telegram_user_id=7001, chat_id=-7001, chat_type="group"
        ),
    )
    assert group_response.status_code == 200
    assert db_session.scalar(select(TelegramIdentity)) is None
    db_session.expire_all()
    token = db_session.scalar(select(TelegramLinkToken))
    assert token is not None and token.used_at is None
    malformed_response = client.post(
        "/api/v1/telegram/webhook",
        headers=headers,
        json=_message_update("/start malformed", telegram_user_id=7001, chat_id=8111),
    )
    assert malformed_response.status_code == 200
    assert db_session.scalar(select(TelegramIdentity)) is None

    private_response = client.post(
        "/api/v1/telegram/webhook",
        headers=headers,
        json=_message_update(
            "/start " + link.token,
            telegram_user_id=7001,
            chat_id=8111,
            chat_type="private",
            username="changeable_name",
        ),
    )
    replay_response = client.post(
        "/api/v1/telegram/webhook",
        headers=headers,
        json=_message_update("/start " + link.token, telegram_user_id=7001, chat_id=8111),
    )

    identity = db_session.scalar(select(TelegramIdentity))
    assert private_response.status_code == replay_response.status_code == 200
    assert identity is not None
    assert identity.telegram_user_id == 7001
    assert identity.user_id == user.id
    assert identity.private_chat_id == 8111
    assert identity.username == "changeable_name"
    assert identity.user_id != identity.telegram_user_id
    assert any("связан" in reply.text.lower() for reply in sent)
    assert sent[-1].text != sent[-2].text

    _as_user(user)
    status_response = client.get("/api/v1/telegram/link-status")
    assert status_response.json()["is_linked"] is True
    assert status_response.json()["username"] == "changeable_name"
    assert family.id == user.family_id


def test_link_tokens_expire_validate_shape_and_reject_replay(db_session: Session) -> None:
    _, user, _ = _seed_user(db_session)
    expired_link = create_telegram_link(db_session, user_id=user.id, bot_username=None)
    expired_row = db_session.scalar(select(TelegramLinkToken))
    assert expired_row is not None
    expired_row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    assert not consume_telegram_link_token(
        db_session,
        raw_token=expired_link.token,
        telegram_user_id=7001,
        private_chat_id=7001,
        profile={},
    )
    assert not consume_telegram_link_token(
        db_session,
        raw_token="malformed",
        telegram_user_id=7001,
        private_chat_id=7001,
        profile={},
    )

    valid_link = create_telegram_link(db_session, user_id=user.id, bot_username=None)
    remaining = valid_link.expires_at - datetime.now(UTC)
    assert timedelta(0) < remaining <= TELEGRAM_LINK_TOKEN_LIFETIME
    first = consume_telegram_link_token(
        db_session,
        raw_token=valid_link.token,
        telegram_user_id=7001,
        private_chat_id=7001,
        profile={},
    )
    replay = consume_telegram_link_token(
        db_session,
        raw_token=valid_link.token,
        telegram_user_id=7001,
        private_chat_id=7001,
        profile={},
    )

    assert first is True
    assert replay is False


def test_active_telegram_identity_cannot_be_reassigned_or_replaced(
    db_session: Session,
    client: TestClient,
) -> None:
    _, user_a, _ = _seed_user(db_session, email="a@example.com", family_name="Family A")
    _, user_b, _ = _seed_user(db_session, email="b@example.com", family_name="Family B")
    link_a = create_telegram_link(db_session, user_id=user_a.id, bot_username=None)
    link_b = create_telegram_link(db_session, user_id=user_b.id, bot_username=None)
    assert consume_telegram_link_token(
        db_session,
        raw_token=link_a.token,
        telegram_user_id=7001,
        private_chat_id=7001,
        profile={"username": "same_name"},
    )

    reassignment = consume_telegram_link_token(
        db_session,
        raw_token=link_b.token,
        telegram_user_id=7001,
        private_chat_id=7001,
        profile={"username": "same_name"},
    )
    _as_user(user_a)
    replacement = client.post("/api/v1/telegram/link-token")

    assert reassignment is False
    assert replacement.status_code == 409
    db_session.expire_all()
    identities = db_session.scalars(select(TelegramIdentity)).all()
    assert len(identities) == 1
    assert identities[0].user_id == user_a.id


def test_unlink_immediately_disables_telegram_context(
    client: TestClient,
    db_session: Session,
) -> None:
    _, user, _ = _seed_user(db_session)
    link = create_telegram_link(db_session, user_id=user.id, bot_username=None)
    assert consume_telegram_link_token(
        db_session,
        raw_token=link.token,
        telegram_user_id=7001,
        private_chat_id=7001,
        profile={},
    )
    _as_user(user)

    response = client.delete("/api/v1/telegram/link")
    context = resolve_telegram_context(
        db_session,
        telegram_user_id=7001,
        private_chat_id=7001,
    )

    assert response.status_code == 204
    assert context is None
    identity = db_session.scalar(select(TelegramIdentity))
    assert identity is not None and identity.is_active is False


def test_default_account_is_family_scoped_active_and_persisted(db_session: Session) -> None:
    family_a, user_a, account_a = _seed_user(db_session, email="a@example.com")
    family_b, user_b, account_b = _seed_user(db_session, email="b@example.com")
    inactive = Account(
        family=family_a,
        owner_user=user_a,
        type="card",
        name="Inactive card",
        currency="UAH",
        is_active=False,
    )
    db_session.add(inactive)
    db_session.commit()
    service = AccountPreferenceService(db_session)

    with pytest.raises(DefaultAccountError):
        service.set_default(user_id=user_a.id, family_id=family_a.id, account_id=account_b.id)
    with pytest.raises(DefaultAccountError):
        service.set_default(user_id=user_a.id, family_id=family_a.id, account_id=inactive.id)
    selected = service.set_default(
        user_id=user_a.id,
        family_id=family_a.id,
        account_id=account_a.id,
    )

    assert selected.id == account_a.id
    assert service.get_default(user_id=user_a.id, family_id=family_a.id).id == account_a.id
    assert service.list_active(family_id=family_a.id) == [account_a]
    assert family_b.id != family_a.id
    assert user_b.family_id == family_b.id


def test_telegram_summary_review_and_forged_callbacks_are_family_scoped(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family_a, user_a, account_a = _seed_user(db_session, email="a@example.com", family_name="A")
    family_b, user_b, account_b = _seed_user(db_session, email="b@example.com", family_name="B")
    transaction_a = _seed_transaction(db_session, family_a, account_a, "A merchant", "-25.00")
    transaction_b = _seed_transaction(db_session, family_b, account_b, "B merchant", "-999.00")
    category_b = Category(family=family_b, name="Private category B")
    db_session.add(category_b)
    db_session.commit()
    for user, telegram_id, chat_id in ((user_a, 7001, 8001), (user_b, 7002, 8002)):
        link = create_telegram_link(db_session, user_id=user.id, bot_username=None)
        assert consume_telegram_link_token(
            db_session,
            raw_token=link.token,
            telegram_user_id=telegram_id,
            private_chat_id=chat_id,
            profile={},
        )
    replies: list[BotReply] = []
    monkeypatch.setattr(
        telegram, "send_bot_replies", lambda _token, rows: replies.extend(rows) or len(rows)
    )

    summary = client.post(
        "/api/v1/telegram/webhook",
        json=_message_update("/summary", telegram_user_id=7001, chat_id=8001),
    )
    assert summary.status_code == 200
    assert "Расходы: 25.00 UAH" in replies[-1].text
    assert "999.00" not in replies[-1].text

    review = client.post(
        "/api/v1/telegram/webhook",
        json=_message_update("/review", telegram_user_id=7001, chat_id=8001),
    )
    assert review.status_code == 200
    assert "A merchant" in replies[-1].text
    assert "B merchant" not in replies[-1].text

    done = client.post(
        "/api/v1/telegram/webhook",
        json=_callback_update(
            f"review_done:{transaction_b.id}",
            telegram_user_id=7001,
            chat_id=8001,
        ),
    )
    category = client.post(
        "/api/v1/telegram/webhook",
        json=_callback_update(
            f"review_category:{transaction_b.id}:{category_b.id}",
            telegram_user_id=7001,
            chat_id=8001,
        ),
    )
    db_session.refresh(transaction_b)

    assert done.status_code == category.status_code == 200
    assert replies[-1].text == REVIEW_TRANSACTION_NOT_FOUND_TEXT
    assert transaction_b.needs_review is True
    assert transaction_b.category_id is None
    assert transaction_a.family_id == family_a.id


def test_manual_telegram_transaction_uses_linked_family_owner_and_default_account(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family, user, account = _seed_user(db_session)
    foreign_family, _, foreign_account = _seed_user(
        db_session,
        email="foreign@example.com",
        family_name="Foreign",
    )
    link = create_telegram_link(db_session, user_id=user.id, bot_username=None)
    assert consume_telegram_link_token(
        db_session,
        raw_token=link.token,
        telegram_user_id=7001,
        private_chat_id=8001,
        profile={},
    )
    replies: list[BotReply] = []
    monkeypatch.setattr(
        telegram, "send_bot_replies", lambda _token, rows: replies.extend(rows) or len(rows)
    )

    no_default = client.post(
        "/api/v1/telegram/webhook",
        json=_message_update("АТБ 450 еда", telegram_user_id=7001, chat_id=8001),
    )
    assert no_default.status_code == 200
    assert "командой /account" in replies[-1].text
    assert db_session.scalar(select(Transaction)) is None

    with pytest.raises(DefaultAccountError):
        AccountPreferenceService(db_session).set_default(
            user_id=user.id,
            family_id=family.id,
            account_id=foreign_account.id,
        )
    listing = client.post(
        "/api/v1/telegram/webhook",
        json=_message_update("/account", telegram_user_id=7001, chat_id=8001),
    )
    assert listing.status_code == 200
    assert replies[-1].reply_markup is not None
    assert len(replies[-1].reply_markup["inline_keyboard"]) == 1

    foreign_selection = client.post(
        "/api/v1/telegram/webhook",
        json=_callback_update(
            f"account_set:{foreign_account.id}",
            telegram_user_id=7001,
            chat_id=8001,
        ),
    )
    assert foreign_selection.status_code == 200
    assert replies[-1].text == ACCOUNT_NOT_FOUND_TEXT
    valid_selection = client.post(
        "/api/v1/telegram/webhook",
        json=_callback_update(
            f"account_set:{account.id}",
            telegram_user_id=7001,
            chat_id=8001,
        ),
    )
    assert valid_selection.status_code == 200
    assert replies[-1].text == ACCOUNT_SELECTED_TEXT
    resolved = resolve_telegram_context(
        db_session,
        telegram_user_id=7001,
        private_chat_id=8001,
    )
    assert resolved is not None and resolved.default_account is not None
    assert resolved.default_account.id == account.id
    observed: list[datetime] = []

    @event.listens_for(db_session, "before_flush")
    def capture_timestamp(session, *_):
        observed.extend(
            row.occurred_at
            for row in session.new
            if isinstance(row, Transaction) and row.occurred_at is not None
        )

    success = client.post(
        "/api/v1/telegram/webhook",
        json=_message_update("АТБ 450 еда", telegram_user_id=7001, chat_id=8001),
    )
    transaction = db_session.scalar(select(Transaction))

    assert success.status_code == 200
    assert "Операция добавлена" in replies[-1].text
    assert transaction is not None
    assert transaction.family_id == family.id
    assert transaction.account_id == account.id
    assert transaction.owner_user_id == user.id
    assert transaction.amount == Decimal("-450.00")
    assert isinstance(transaction.amount, Decimal)
    assert observed and observed[0].tzinfo is UTC
    assert Transaction.__table__.c.occurred_at.type.timezone is True
    assert foreign_family.id != family.id


def test_unlink_service_invalidates_unconsumed_tokens(db_session: Session) -> None:
    _, user, _ = _seed_user(db_session)
    link = create_telegram_link(db_session, user_id=user.id, bot_username=None)

    assert unlink_telegram_identity(db_session, user_id=user.id) is False
    db_session.expire_all()
    token = db_session.scalar(select(TelegramLinkToken))

    assert token is not None
    assert token.used_at is not None
    assert not consume_telegram_link_token(
        db_session,
        raw_token=link.token,
        telegram_user_id=7001,
        private_chat_id=7001,
        profile={},
    )


def test_production_requires_webhook_secret_when_telegram_is_enabled() -> None:
    with pytest.raises(ValueError, match="TELEGRAM_WEBHOOK_SECRET_TOKEN"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret_key="s" * 32,
            auth_cookie_secure=True,
            telegram_bot_token="bot-token",
        )


def _as_user(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _seed_user(
    db_session: Session,
    *,
    email: str = "telegram@example.com",
    family_name: str = "Telegram Family",
) -> tuple[Family, User, Account]:
    family = Family(name=family_name)
    user = User(family=family, email=email, password_hash="hash", display_name="Owner")
    account = Account(
        family=family,
        owner_user=user,
        type="card",
        name="Main card",
        currency="UAH",
    )
    db_session.add_all([family, user, account])
    db_session.commit()
    return family, user, account


def _seed_transaction(
    db_session: Session,
    family: Family,
    account: Account,
    description: str,
    amount: str,
) -> Transaction:
    transaction = Transaction(
        family=family,
        account=account,
        occurred_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
        amount=Decimal(amount),
        currency="UAH",
        direction="expense",
        flow_type="purchase",
        scope="family",
        description_normalized=description,
        needs_review=True,
    )
    db_session.add(transaction)
    db_session.commit()
    return transaction


def _message_update(
    text: str,
    *,
    telegram_user_id: int,
    chat_id: int,
    chat_type: str = "private",
    username: str | None = None,
) -> dict:
    sender = {"id": telegram_user_id}
    if username:
        sender["username"] = username
    return {
        "message": {
            "chat": {"id": chat_id, "type": chat_type},
            "from": sender,
            "text": text,
        }
    }


def _callback_update(data: str, *, telegram_user_id: int, chat_id: int) -> dict:
    return {
        "callback_query": {
            "id": "callback-1",
            "from": {"id": telegram_user_id},
            "data": data,
            "message": {"chat": {"id": chat_id, "type": "private"}},
        }
    }
