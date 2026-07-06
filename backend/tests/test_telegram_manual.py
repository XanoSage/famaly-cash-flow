from collections.abc import Generator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.models.account import Account
from app.models.category import Category
from app.models.family import Family
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.models.user import User
from app.telegram_bot.manual import (
    MANUAL_ACCOUNT_NOT_FOUND_TEXT,
    MANUAL_CREATED_REVIEW_TEXT,
    MANUAL_CREATED_TEXT,
    MANUAL_INVALID_CONFIG_TEXT,
    MANUAL_NOT_CONFIGURED_TEXT,
    MANUAL_PARSE_USAGE_TEXT,
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


def test_create_manual_transaction_creates_categorized_expense(db_session: Session) -> None:
    family, account, category = _seed_manual_family(db_session)

    text = create_manual_transaction_text(
        db_session,
        family_id_value=str(family.id),
        account_id_value=str(account.id),
        text="АТБ 450 еда",
    )

    transaction = db_session.scalar(select(Transaction))
    merchant = db_session.scalar(select(Merchant))
    assert text.startswith(MANUAL_CREATED_TEXT)
    assert transaction is not None
    assert transaction.family_id == family.id
    assert transaction.account_id == account.id
    assert transaction.amount == Decimal("-450.00")
    assert transaction.currency == "UAH"
    assert transaction.direction == "expense"
    assert transaction.flow_type == "purchase"
    assert transaction.scope == "family"
    assert transaction.description_normalized == "АТБ"
    assert transaction.category_id == category.id
    assert transaction.needs_review is False
    assert merchant is not None
    assert merchant.name == "АТБ"


def test_create_manual_transaction_marks_uncategorized_for_review(db_session: Session) -> None:
    family, account, _ = _seed_manual_family(db_session)

    text = create_manual_transaction_text(
        db_session,
        family_id_value=str(family.id),
        account_id_value=str(account.id),
        text="Рынок 120 неизвестно",
    )

    transaction = db_session.scalar(select(Transaction))
    assert text.startswith(MANUAL_CREATED_REVIEW_TEXT)
    assert transaction is not None
    assert transaction.category_id is None
    assert transaction.needs_review is True


def test_create_manual_transaction_validates_config_and_account(db_session: Session) -> None:
    family, _, _ = _seed_manual_family(db_session)

    assert (
        create_manual_transaction_text(
            db_session,
            family_id_value=None,
            account_id_value=None,
            text="АТБ 450 еда",
        )
        == MANUAL_NOT_CONFIGURED_TEXT
    )
    assert (
        create_manual_transaction_text(
            db_session,
            family_id_value="not-a-uuid",
            account_id_value="also-not-a-uuid",
            text="АТБ 450 еда",
        )
        == MANUAL_INVALID_CONFIG_TEXT
    )
    assert (
        create_manual_transaction_text(
            db_session,
            family_id_value=str(family.id),
            account_id_value="00000000-0000-0000-0000-000000000000",
            text="АТБ 450 еда",
        )
        == MANUAL_ACCOUNT_NOT_FOUND_TEXT
    )


def test_create_manual_transaction_validates_text(db_session: Session) -> None:
    family, account, _ = _seed_manual_family(db_session)

    assert (
        create_manual_transaction_text(
            db_session,
            family_id_value=str(family.id),
            account_id_value=str(account.id),
            text="АТБ еда",
        )
        == MANUAL_PARSE_USAGE_TEXT
    )


def _seed_manual_family(db_session: Session) -> tuple[Family, Account, Category]:
    family = Family(name="Manual Family")
    user = User(
        family=family,
        email="manual-owner@example.com",
        password_hash="hash",
        display_name="Owner",
    )
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
    return family, account, category
