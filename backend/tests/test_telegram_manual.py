from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.family import Family
from app.models.transaction import Transaction
from app.models.user import User
from app.services.transactions import TransactionService
from app.telegram_bot.context import TelegramRequestContext
from app.telegram_bot.manual import (
    MANUAL_CASH_WALLET_MISSING_TEXT,
    MANUAL_CREATED_REVIEW_TEXT,
    MANUAL_CREATED_TEXT,
    MANUAL_PARSE_USAGE_TEXT,
    MANUAL_SELECT_ACCOUNT_TEXT,
    create_manual_transaction_text,
    parse_manual_transaction,
)


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


def test_parse_manual_transaction_reads_description_amount_and_category() -> None:
    draft = parse_manual_transaction("АТБ 450,50 еда")

    assert draft is not None
    assert draft.description == "АТБ"
    assert draft.amount == Decimal("450.50")
    assert draft.category_hint == "еда"


def test_parse_manual_transaction_rejects_commands_or_missing_amount() -> None:
    assert parse_manual_transaction("/summary") is None
    assert parse_manual_transaction("АТБ еда") is None
    assert parse_manual_transaction("АТБ 0 еда") is None


def test_parse_manual_income_command_accepts_only_positive_money() -> None:
    draft = parse_manual_transaction("/income 25000,50 Зарплата")

    assert draft is not None
    assert draft.direction == "income"
    assert draft.amount == Decimal("25000.50")
    assert draft.description == "Зарплата"
    assert draft.income_type == "income"
    assert parse_manual_transaction("/income -25 Зарплата") is None
    assert parse_manual_transaction("/income 0 Зарплата") is None


def test_parse_cash_expense_command_uses_decimal_and_description() -> None:
    draft = parse_manual_transaction("/cash 450,50 Рынок")

    assert draft is not None
    assert draft.amount == Decimal("450.50")
    assert draft.description == "Рынок"
    assert draft.cash_expense is True
    assert parse_manual_transaction("/cash -450 Рынок") is None
    assert parse_manual_transaction("/cash 450") is None


def test_telegram_cash_expense_uses_family_wallet_without_default_account(
    db_session: Session,
) -> None:
    family, user, _, _ = _seed_family(db_session)
    TransactionService(db_session).ensure_cash_wallet(user=user)
    reply = create_manual_transaction_text(
        db_session,
        context=_context(user, family, None),
        text="/cash 450 Рынок",
    )

    transaction = db_session.scalar(select(Transaction))
    wallet = TransactionService(db_session).get_cash_wallet(user=user)
    assert transaction is not None and wallet is not None
    assert transaction.account_id == wallet.id
    assert transaction.family_id == family.id
    assert transaction.amount == Decimal("-450.00")
    assert transaction.direction == "expense"
    assert transaction.flow_type == "cash_expense"
    assert reply.startswith("Расход наличными записан.")
    assert "-450.00 UAH" in reply


def test_telegram_cash_expense_requires_wallet_setup_in_web(db_session: Session) -> None:
    family, user, _, _ = _seed_family(db_session)

    reply = create_manual_transaction_text(
        db_session,
        context=_context(user, family, None),
        text="/cash 450 Рынок",
    )

    assert reply == MANUAL_CASH_WALLET_MISSING_TEXT
    assert db_session.scalar(select(Transaction)) is None


def test_telegram_income_uses_shared_service_and_persists_audit(
    db_session: Session,
) -> None:
    family, user, account, _ = _seed_family(db_session)

    reply = create_manual_transaction_text(
        db_session,
        context=_context(user, family, account),
        text="/income 25000 Зарплата",
    )

    transaction = db_session.scalar(select(Transaction))
    audit = db_session.scalar(select(AuditLog))
    assert reply.startswith(MANUAL_CREATED_REVIEW_TEXT)
    assert transaction is not None
    assert transaction.family_id == family.id
    assert transaction.owner_user_id == user.id
    assert transaction.amount == Decimal("25000.00")
    assert transaction.direction == "income"
    assert transaction.flow_type == "income"
    assert transaction.income_type == "income"
    assert transaction.description_raw == "/income 25000 Зарплата"
    assert transaction.description_override == "Зарплата"
    assert audit is not None
    assert audit.user_id == user.id
    assert audit.family_id == family.id
    assert audit.action == "create"
    assert audit.after_payload["amount"] == "25000.00"


def test_manual_transaction_uses_linked_user_family_default_and_aware_utc(
    db_session: Session,
) -> None:
    family, user, account, category = _seed_family(db_session)
    observed: list[datetime] = []

    @event.listens_for(db_session, "before_flush")
    def capture_timestamp(session, *_):
        observed.extend(
            item.occurred_at
            for item in session.new
            if isinstance(item, Transaction) and item.occurred_at is not None
        )

    context = _context(user, family, account)
    reply = create_manual_transaction_text(db_session, context=context, text="АТБ 450 еда")
    transaction = db_session.scalar(select(Transaction))

    assert reply.startswith(MANUAL_CREATED_TEXT)
    assert transaction is not None
    assert transaction.family_id == family.id
    assert transaction.account_id == account.id
    assert transaction.owner_user_id == user.id
    assert transaction.amount == Decimal("-450.00")
    assert isinstance(transaction.amount, Decimal)
    assert transaction.category_id == category.id
    assert transaction.needs_review is False
    assert observed and observed[0].tzinfo is UTC
    assert Transaction.__table__.c.occurred_at.type.timezone is True


def test_manual_transaction_without_default_account_is_rejected_safely(
    db_session: Session,
) -> None:
    family, user, _, _ = _seed_family(db_session)

    reply = create_manual_transaction_text(
        db_session,
        context=_context(user, family, None),
        text="АТБ 450 еда",
    )

    assert reply == MANUAL_SELECT_ACCOUNT_TEXT
    assert db_session.scalar(select(Transaction)) is None


def test_manual_transaction_revalidates_selected_account_family(db_session: Session) -> None:
    family, user, _, _ = _seed_family(db_session)
    other_family, other_user, foreign_account, _ = _seed_family(
        db_session,
        email="other@example.com",
        name="Other Family",
    )

    reply = create_manual_transaction_text(
        db_session,
        context=_context(user, family, foreign_account),
        text="АТБ 450 еда",
    )

    assert reply == MANUAL_SELECT_ACCOUNT_TEXT
    assert db_session.scalar(select(Transaction)) is None
    assert other_family.id != family.id
    assert foreign_account.owner_user_id == other_user.id


def test_manual_transaction_validates_text(db_session: Session) -> None:
    family, user, account, _ = _seed_family(db_session)

    reply = create_manual_transaction_text(
        db_session,
        context=_context(user, family, account),
        text="АТБ еда",
    )

    assert reply == MANUAL_PARSE_USAGE_TEXT
    assert db_session.scalar(select(Transaction)) is None


def _context(user: User, family: Family, account: Account | None) -> TelegramRequestContext:
    return TelegramRequestContext(
        identity=SimpleNamespace(telegram_user_id=1001),
        user=user,
        family=family,
        private_chat_id=1001,
        default_account=account,
    )


def _seed_family(
    db_session: Session,
    *,
    email: str = "manual-owner@example.com",
    name: str = "Manual Family",
) -> tuple[Family, User, Account, Category]:
    family = Family(name=name)
    user = User(family=family, email=email, password_hash="hash", display_name="Owner")
    account = Account(
        family=family,
        owner_user=user,
        type="card",
        name="Main card",
        currency="UAH",
    )
    category = Category(family=family, name="Еда")
    db_session.add_all([family, user, account, category])
    db_session.commit()
    return family, user, account, category
