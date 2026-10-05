from collections.abc import Generator
from datetime import UTC, datetime
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
from app.models.transaction import Transaction
from app.models.user import User
from app.telegram_bot.review import (
    REVIEW_CATEGORY_ASSIGNED_TEXT,
    REVIEW_MARKED_DONE_TEXT,
    REVIEW_TRANSACTION_NOT_FOUND_TEXT,
    assign_category_text,
    build_category_menu_content,
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


def test_review_lists_only_family_rows_and_exposes_safe_action_callbacks(
    db_session: Session,
) -> None:
    family_a, _, transaction_a, _, _ = _seed_review_row(db_session, "a@example.com", "Family A")
    _seed_review_row(db_session, "b@example.com", "Family B")

    reply = build_review_reply_content(db_session, family_a.id)

    assert "Family A merchant" in reply.text
    assert "Family B merchant" not in reply.text
    assert reply.reply_markup is not None
    assert reply.reply_markup["inline_keyboard"][0][0]["callback_data"] == (
        f"review_done:{transaction_a.id}"
    )


def test_mark_reviewed_and_category_assignment_are_family_scoped(db_session: Session) -> None:
    family_a, _, _, _, _ = _seed_review_row(db_session, "a@example.com", "Family A")
    family_b, _, transaction_b, category_b, _ = _seed_review_row(
        db_session, "b@example.com", "Family B"
    )

    assert mark_reviewed_text(db_session, family_a.id, str(transaction_b.id)) == (
        REVIEW_TRANSACTION_NOT_FOUND_TEXT
    )
    assert (
        assign_category_text(
            db_session,
            family_a.id,
            str(transaction_b.id),
            str(category_b.id),
        )
        == REVIEW_TRANSACTION_NOT_FOUND_TEXT
    )
    db_session.refresh(transaction_b)
    assert transaction_b.needs_review is True
    assert transaction_b.category_id is None

    assert mark_reviewed_text(db_session, family_b.id, str(transaction_b.id)) == (
        REVIEW_MARKED_DONE_TEXT
    )
    db_session.refresh(transaction_b)
    assert transaction_b.needs_review is False


def test_review_category_menu_and_assignment_share_review_service(db_session: Session) -> None:
    family, _, transaction, category, _ = _seed_review_row(db_session, "a@example.com", "Family A")

    menu = build_category_menu_content(db_session, family.id, str(transaction.id))
    result = assign_category_text(
        db_session,
        family.id,
        str(transaction.id),
        str(category.id),
    )

    assert menu.reply_markup is not None
    assert menu.reply_markup["inline_keyboard"][0][0]["callback_data"].startswith(
        "review_category:"
    )
    assert result == REVIEW_CATEGORY_ASSIGNED_TEXT
    db_session.refresh(transaction)
    assert transaction.category_id == category.id
    assert transaction.needs_review is False


def _seed_review_row(
    db_session: Session,
    email: str,
    family_name: str,
) -> tuple[Family, User, Transaction, Category, Account]:
    family = Family(name=family_name)
    user = User(family=family, email=email, password_hash="hash", display_name="Owner")
    account = Account(family=family, owner_user=user, type="card", name="Card", currency="UAH")
    category = Category(family=family, name=f"{family_name} category")
    transaction = Transaction(
        family=family,
        account=account,
        occurred_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
        amount=Decimal("-120.00"),
        currency="UAH",
        direction="expense",
        flow_type="purchase",
        scope="family",
        description_normalized=f"{family_name} merchant",
        needs_review=True,
    )
    db_session.add_all([family, user, account, category, transaction])
    db_session.commit()
    return family, user, transaction, category, account
