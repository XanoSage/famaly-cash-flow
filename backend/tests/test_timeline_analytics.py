from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.analytics.timeline import TimelineAnalyticsService
from app.db.base import Base
from app.models.account import Account
from app.models.family import Family
from app.models.transaction import Transaction
from app.models.user import User


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session


def test_timeline_groups_money_flow_by_day(db_session: Session) -> None:
    family, _ = _seed_timeline_transactions(db_session)

    analytics = TimelineAnalyticsService(db_session).build(family_id=family.id)

    assert analytics.granularity == "day"
    assert [row.period.isoformat() for row in analytics.rows] == ["2026-05-01", "2026-05-02", "2026-05-03"]

    first_day = analytics.rows[0]
    assert first_day.income == Decimal("1000.00")
    assert first_day.expenses == Decimal("150.00")
    assert first_day.savings == Decimal("50.00")
    assert first_day.transfers == Decimal("0.00")
    assert first_day.net_cash_flow == Decimal("800.00")
    assert first_day.transaction_count == 3
    assert first_day.expense_count == 1
    assert first_day.income_count == 1
    assert first_day.savings_count == 1

    second_day = analytics.rows[1]
    assert second_day.expenses == Decimal("200.00")
    assert second_day.transfers == Decimal("300.00")
    assert second_day.net_cash_flow == Decimal("-200.00")
    assert second_day.transaction_count == 2
    assert second_day.transfer_count == 1


def test_timeline_filters_by_period_scope_and_account(db_session: Session) -> None:
    family, account = _seed_timeline_transactions(db_session)

    analytics = TimelineAnalyticsService(db_session).build(
        family_id=family.id,
        account_id=account.id,
        occurred_from=datetime(2026, 5, 2),
        occurred_to=datetime(2026, 5, 2, 23, 59),
        scope="work_fop",
    )

    assert len(analytics.rows) == 1
    assert analytics.rows[0].period.isoformat() == "2026-05-02"
    assert analytics.rows[0].expenses == Decimal("200.00")
    assert analytics.rows[0].transfers == Decimal("0.00")
    assert analytics.rows[0].transaction_count == 1


def _seed_timeline_transactions(db_session: Session) -> tuple[Family, Account]:
    family = Family(name="Test Family")
    user = User(
        family=family,
        email="owner@example.com",
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
    other_account = Account(
        family=family,
        owner_user=user,
        type="cash",
        name="Cash",
        currency="UAH",
    )
    transactions = [
        Transaction(
            family=family,
            account=account,
            occurred_at=datetime(2026, 5, 1, 9, 0),
            amount=Decimal("1000.00"),
            currency="UAH",
            direction="income",
            flow_type="income",
            scope="family",
            description_raw="Salary",
        ),
        Transaction(
            family=family,
            account=account,
            occurred_at=datetime(2026, 5, 1, 10, 0),
            amount=Decimal("-150.00"),
            currency="UAH",
            direction="expense",
            flow_type="purchase",
            scope="family",
            description_raw="Food",
        ),
        Transaction(
            family=family,
            account=account,
            occurred_at=datetime(2026, 5, 1, 11, 0),
            amount=Decimal("-50.00"),
            currency="UAH",
            direction="expense",
            flow_type="transfer_to_savings",
            scope="family",
            description_raw="Savings jar",
        ),
        Transaction(
            family=family,
            account=account,
            occurred_at=datetime(2026, 5, 2, 10, 0),
            amount=Decimal("-200.00"),
            currency="UAH",
            direction="expense",
            flow_type="purchase",
            scope="work_fop",
            description_raw="Hosting",
        ),
        Transaction(
            family=family,
            account=account,
            occurred_at=datetime(2026, 5, 2, 11, 0),
            amount=Decimal("-300.00"),
            currency="UAH",
            direction="expense",
            flow_type="person_transfer",
            scope="family",
            description_raw="Transfer",
        ),
        Transaction(
            family=family,
            account=other_account,
            occurred_at=datetime(2026, 5, 3, 12, 0),
            amount=Decimal("-80.00"),
            currency="UAH",
            direction="expense",
            flow_type="purchase",
            scope="family",
            description_raw="Cash lunch",
        ),
        Transaction(
            family=family,
            account=account,
            occurred_at=datetime(2026, 5, 4, 12, 0),
            amount=Decimal("-900.00"),
            currency="UAH",
            direction="expense",
            flow_type="purchase",
            scope="family",
            deleted_at=datetime(2026, 5, 4, 13, 0),
            description_raw="Deleted",
        ),
    ]
    db_session.add_all([family, user, account, other_account, *transactions])
    db_session.commit()
    return family, account
