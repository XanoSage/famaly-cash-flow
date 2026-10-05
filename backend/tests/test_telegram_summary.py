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
from app.models.family import Family
from app.models.transaction import Transaction
from app.models.user import User
from app.telegram_bot.summary import build_summary_text


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


def test_build_summary_text_uses_shared_analytics_service(db_session: Session) -> None:
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
                occurred_at=datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
                amount=Decimal("1000.00"),
                currency="UAH",
                direction="income",
                flow_type="income",
                scope="family",
            ),
            Transaction(
                family=family,
                account=account,
                occurred_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
                amount=Decimal("-100.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
                needs_review=True,
            ),
        ]
    )
    db_session.commit()

    text = build_summary_text(db_session, family.id)

    assert "Сводка Family Cash Flow" in text
    assert "Доходы: 1 000.00 UAH" in text
    assert "Расходы: 100.00 UAH" in text
    assert "Cash flow: 900.00 UAH" in text
    assert "Операций: 2" in text
    assert "На проверку: 1" in text
