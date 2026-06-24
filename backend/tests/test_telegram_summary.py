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
from app.models.family import Family
from app.models.transaction import Transaction
from app.models.user import User
from app.telegram_bot.summary import (
    SUMMARY_INVALID_FAMILY_ID_TEXT,
    SUMMARY_NOT_CONFIGURED_TEXT,
    build_summary_text,
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


def test_build_summary_text_returns_configuration_message_without_family_id(
    db_session: Session,
) -> None:
    assert build_summary_text(db_session, None) == SUMMARY_NOT_CONFIGURED_TEXT
    assert build_summary_text(db_session, "") == SUMMARY_NOT_CONFIGURED_TEXT


def test_build_summary_text_returns_invalid_family_id_message(db_session: Session) -> None:
    assert build_summary_text(db_session, "not-a-uuid") == SUMMARY_INVALID_FAMILY_ID_TEXT


def test_build_summary_text_formats_analytics_summary(db_session: Session) -> None:
    family = _seed_summary_transactions(db_session)

    text = build_summary_text(db_session, str(family.id))

    assert "Сводка Family Cash Flow" in text
    assert "Доходы: 1 000.00 UAH" in text
    assert "Расходы: 100.00 UAH" in text
    assert "Накопления: 50.00 UAH" in text
    assert "Cash flow: 850.00 UAH" in text
    assert "Операций: 4" in text
    assert "На проверку: 1" in text
    assert "Без категории: 1" in text


def _seed_summary_transactions(db_session: Session) -> Family:
    family = Family(name="Telegram Family")
    user = User(
        family=family,
        email="telegram-owner@example.com",
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
    db_session.add_all(
        [
            family,
            user,
            account,
            Transaction(
                family=family,
                account=account,
                occurred_at=datetime(2026, 5, 1, 9, 0),
                amount=Decimal("1000.00"),
                currency="UAH",
                direction="income",
                flow_type="income",
                scope="family",
            ),
            Transaction(
                family=family,
                account=account,
                occurred_at=datetime(2026, 5, 1, 10, 0),
                amount=Decimal("-100.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
                needs_review=True,
            ),
            Transaction(
                family=family,
                account=account,
                occurred_at=datetime(2026, 5, 2, 10, 0),
                amount=Decimal("-50.00"),
                currency="UAH",
                direction="expense",
                flow_type="transfer_to_savings",
                scope="family",
            ),
            Transaction(
                family=family,
                account=account,
                occurred_at=datetime(2026, 5, 3, 10, 0),
                amount=Decimal("-200.00"),
                currency="UAH",
                direction="expense",
                flow_type="person_transfer",
                scope="family",
            ),
        ]
    )
    db_session.commit()
    return family
