from collections.abc import Generator
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
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
from app.telegram_bot.review import (
    REVIEW_ALREADY_DONE_TEXT,
    REVIEW_CATEGORIES_EMPTY_TEXT,
    REVIEW_CATEGORY_ASSIGNED_TEXT,
    REVIEW_CATEGORY_NOT_FOUND_TEXT,
    REVIEW_CATEGORY_USAGE_TEXT,
    REVIEW_DONE_USAGE_TEXT,
    REVIEW_EMPTY_TEXT,
    REVIEW_INVALID_FAMILY_ID_TEXT,
    REVIEW_MARKED_DONE_TEXT,
    REVIEW_NOT_CONFIGURED_TEXT,
    REVIEW_TRANSACTION_NOT_FOUND_TEXT,
    assign_category_text,
    build_category_menu_content,
    build_review_text,
    build_review_reply_content,
    mark_reviewed_text,
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


def test_build_review_text_returns_configuration_message_without_family_id(
    db_session: Session,
) -> None:
    assert build_review_text(db_session, None) == REVIEW_NOT_CONFIGURED_TEXT
    assert build_review_text(db_session, "") == REVIEW_NOT_CONFIGURED_TEXT


def test_build_review_text_returns_invalid_family_id_message(db_session: Session) -> None:
    assert build_review_text(db_session, "not-a-uuid") == REVIEW_INVALID_FAMILY_ID_TEXT


def test_build_review_text_returns_empty_message(db_session: Session) -> None:
    family = Family(name="Empty Review Family")
    db_session.add(family)
    db_session.commit()

    assert build_review_text(db_session, str(family.id)) == REVIEW_EMPTY_TEXT


def test_build_review_text_formats_review_transactions(db_session: Session) -> None:
    family = _seed_review_transactions(db_session)

    text = build_review_text(db_session, str(family.id))

    assert "Операции на проверку" in text
    assert "1. 03.05.2026 | id: " in text
    assert "| -250.00 UAH | Медцентр | Здоровье" in text
    assert "2. 02.05.2026 | id: " in text
    assert "| -100.00 UAH | Need category | без категории" in text
    assert "Reviewed already" not in text


def test_build_review_reply_content_adds_inline_buttons(db_session: Session) -> None:
    family = _seed_review_transactions(db_session)

    reply = build_review_reply_content(db_session, str(family.id))

    assert "Операции на проверку" in reply.text
    assert reply.reply_markup is not None
    keyboard = reply.reply_markup["inline_keyboard"]
    assert keyboard[0][0]["text"] == "Готово 1"
    assert keyboard[0][0]["callback_data"].startswith("review_done:")
    assert keyboard[0][1]["text"] == "Категория 1"
    assert keyboard[0][1]["callback_data"].startswith("review_categories:")
    assert keyboard[1][0]["text"] == "Готово 2"
    assert len(keyboard[0][1]["callback_data"]) <= 64


def test_build_review_reply_content_skips_inline_buttons_for_empty_queue(
    db_session: Session,
) -> None:
    family = Family(name="Empty Review Family")
    db_session.add(family)
    db_session.commit()

    reply = build_review_reply_content(db_session, str(family.id))

    assert reply.text == REVIEW_EMPTY_TEXT
    assert reply.reply_markup is None


def test_build_category_menu_content_returns_category_buttons(db_session: Session) -> None:
    family = _seed_review_transactions(db_session)
    review_reply = build_review_reply_content(db_session, str(family.id))
    transaction_token = review_reply.reply_markup["inline_keyboard"][0][1]["callback_data"].split(":", 1)[1]

    category_reply = build_category_menu_content(db_session, str(family.id), transaction_token)

    assert category_reply.text.startswith("Выбери категорию")
    assert category_reply.reply_markup is not None
    keyboard = category_reply.reply_markup["inline_keyboard"]
    assert keyboard[0][0]["text"] == "Здоровье"
    assert keyboard[0][0]["callback_data"].startswith("review_category:")
    assert len(keyboard[0][0]["callback_data"]) <= 64


def test_build_category_menu_content_returns_empty_message_without_categories(
    db_session: Session,
) -> None:
    family = Family(name="No Categories Family")
    user = User(
        family=family,
        email="no-categories@example.com",
        password_hash="hash",
        display_name="Owner",
    )
    account = Account(family=family, owner_user=user, type="card", name="Main", currency="UAH")
    transaction = Transaction(
        family=family,
        account=account,
        occurred_at=datetime(2026, 5, 1, 10, 0),
        amount=Decimal("-100.00"),
        currency="UAH",
        direction="expense",
        flow_type="purchase",
        scope="family",
        needs_review=True,
    )
    db_session.add_all([family, user, account, transaction])
    db_session.commit()
    token = _category_menu_token(db_session, family)

    reply = build_category_menu_content(db_session, str(family.id), token)

    assert reply.text == REVIEW_CATEGORIES_EMPTY_TEXT
    assert reply.reply_markup is None


def test_assign_category_text_sets_category_and_marks_done(db_session: Session) -> None:
    family = _seed_review_transactions(db_session)
    transaction = _latest_review_transaction(db_session, family)
    review_reply = build_review_reply_content(db_session, str(family.id))
    transaction_token = review_reply.reply_markup["inline_keyboard"][0][1]["callback_data"].split(":", 1)[1]
    category_reply = build_category_menu_content(db_session, str(family.id), transaction_token)
    _, callback_payload = category_reply.reply_markup["inline_keyboard"][0][0]["callback_data"].split(":", 1)
    transaction_token, category_token = callback_payload.split(":", 1)

    text = assign_category_text(db_session, str(family.id), transaction_token, category_token)

    db_session.refresh(transaction)
    assert text == REVIEW_CATEGORY_ASSIGNED_TEXT
    assert transaction.category is not None
    assert transaction.category.name == "Здоровье"
    assert transaction.needs_review is False


def test_assign_category_text_validates_input(db_session: Session) -> None:
    family = _seed_review_transactions(db_session)
    token = _category_menu_token(db_session, family)

    assert assign_category_text(db_session, None, None, None) == REVIEW_NOT_CONFIGURED_TEXT
    assert assign_category_text(db_session, str(family.id), None, None) == REVIEW_CATEGORY_USAGE_TEXT
    assert (
        assign_category_text(db_session, str(family.id), token, "00000000-0000-0000-0000-000000000000")
        == REVIEW_CATEGORY_NOT_FOUND_TEXT
    )


def test_build_review_text_applies_limit(db_session: Session) -> None:
    family = _seed_review_transactions(db_session)

    text = build_review_text(db_session, str(family.id), limit=1)

    assert "1. 03.05.2026 | id: " in text
    assert "| -250.00 UAH | Медцентр | Здоровье" in text
    assert "2. " not in text


def test_mark_reviewed_text_marks_transaction_done(db_session: Session) -> None:
    family = _seed_review_transactions(db_session)
    transaction = _latest_review_transaction(db_session, family)

    text = mark_reviewed_text(db_session, str(family.id), str(transaction.id))

    db_session.refresh(transaction)
    assert text == REVIEW_MARKED_DONE_TEXT
    assert transaction.needs_review is False


def test_mark_reviewed_text_returns_already_done_message(db_session: Session) -> None:
    family = _seed_review_transactions(db_session)
    transaction = _reviewed_transaction(db_session, family)

    text = mark_reviewed_text(db_session, str(family.id), str(transaction.id))

    assert text == REVIEW_ALREADY_DONE_TEXT


def test_mark_reviewed_text_validates_input(db_session: Session) -> None:
    family = _seed_review_transactions(db_session)

    assert mark_reviewed_text(db_session, None, None) == REVIEW_NOT_CONFIGURED_TEXT
    assert mark_reviewed_text(db_session, "not-a-uuid", None) == REVIEW_INVALID_FAMILY_ID_TEXT
    assert mark_reviewed_text(db_session, str(family.id), None) == REVIEW_DONE_USAGE_TEXT
    assert mark_reviewed_text(db_session, str(family.id), "not-a-uuid") == REVIEW_DONE_USAGE_TEXT
    assert (
        mark_reviewed_text(
            db_session,
            str(family.id),
            "00000000-0000-0000-0000-000000000000",
        )
        == REVIEW_TRANSACTION_NOT_FOUND_TEXT
    )


def _seed_review_transactions(db_session: Session) -> Family:
    family = Family(name="Telegram Review Family")
    user = User(
        family=family,
        email="telegram-review-owner@example.com",
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
    merchant = Merchant(
        family=family,
        name="Медцентр",
        normalized_name="medcenter",
        merchant_type="health",
    )
    category = Category(
        family=family,
        name="Здоровье",
    )
    db_session.add_all(
        [
            family,
            user,
            account,
            merchant,
            category,
            Transaction(
                family=family,
                account=account,
                occurred_at=datetime(2026, 5, 1, 10, 0),
                amount=Decimal("-50.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
                comment="Reviewed already",
                needs_review=False,
            ),
            Transaction(
                family=family,
                account=account,
                occurred_at=datetime(2026, 5, 2, 10, 0),
                amount=Decimal("-100.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
                comment="Need category",
                needs_review=True,
            ),
            Transaction(
                family=family,
                account=account,
                merchant=merchant,
                category=category,
                occurred_at=datetime(2026, 5, 3, 10, 0),
                amount=Decimal("-250.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
                needs_review=True,
            ),
        ]
    )
    db_session.commit()
    return family


def _latest_review_transaction(db_session: Session, family: Family) -> Transaction:
    return (
        db_session.query(Transaction)
        .filter(Transaction.family_id == family.id, Transaction.needs_review.is_(True))
        .order_by(Transaction.occurred_at.desc())
        .first()
    )


def _reviewed_transaction(db_session: Session, family: Family) -> Transaction:
    return (
        db_session.query(Transaction)
        .filter(Transaction.family_id == family.id, Transaction.needs_review.is_(False))
        .first()
    )


def _category_menu_token(db_session: Session, family: Family) -> str:
    reply = build_review_reply_content(db_session, str(family.id))
    return reply.reply_markup["inline_keyboard"][0][1]["callback_data"].split(":", 1)[1]
