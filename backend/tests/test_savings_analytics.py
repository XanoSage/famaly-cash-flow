from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.analytics.savings import SavingsAnalyticsService
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


def test_savings_analytics_builds_totals_projection_and_timeline(db_session: Session) -> None:
    family, _ = _seed_savings_transactions(db_session)

    analytics = SavingsAnalyticsService(db_session).build(family_id=family.id)

    assert analytics.total_savings == Decimal("150.00")
    assert analytics.total_expenses == Decimal("450.00")
    assert analytics.savings_count == 2
    assert analytics.expense_count == 3
    assert analytics.savings_to_expenses_percent == Decimal("33.33")
    assert analytics.period_days == 3
    assert analytics.average_daily_savings == Decimal("50.00")
    assert analytics.projected_yearly_savings == Decimal("18250.00")
    assert [row.period.isoformat() for row in analytics.rows] == [
        "2026-05-01",
        "2026-05-02",
        "2026-05-03",
    ]
    assert analytics.rows[0].savings == Decimal("50.00")
    assert analytics.rows[0].expenses == Decimal("100.00")
    assert analytics.rows[1].savings == Decimal("100.00")
    assert analytics.rows[2].expenses == Decimal("350.00")


def test_savings_analytics_filters_by_scope_and_account(db_session: Session) -> None:
    family, account = _seed_savings_transactions(db_session)

    analytics = SavingsAnalyticsService(db_session).build(
        family_id=family.id,
        account_id=account.id,
        scope="work_fop",
    )

    assert analytics.total_savings == Decimal("0.00")
    assert analytics.total_expenses == Decimal("200.00")
    assert analytics.period_days == 1
    assert analytics.rows[0].period.isoformat() == "2026-05-03"


def _seed_savings_transactions(db_session: Session) -> tuple[Family, Account]:
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
    cash_account = Account(
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
            occurred_at=datetime(2026, 5, 1, 10, 0),
            amount=Decimal("-50.00"),
            currency="UAH",
            direction="expense",
            flow_type="transfer_to_savings",
            scope="family",
        ),
        Transaction(
            family=family,
            account=account,
            occurred_at=datetime(2026, 5, 1, 11, 0),
            amount=Decimal("-100.00"),
            currency="UAH",
            direction="expense",
            flow_type="purchase",
            scope="family",
        ),
        Transaction(
            family=family,
            account=account,
            occurred_at=datetime(2026, 5, 2, 10, 0),
            amount=Decimal("-100.00"),
            currency="UAH",
            direction="expense",
            flow_type="transfer_to_savings",
            scope="family",
        ),
        Transaction(
            family=family,
            account=cash_account,
            occurred_at=datetime(2026, 5, 3, 10, 0),
            amount=Decimal("-150.00"),
            currency="UAH",
            direction="expense",
            flow_type="purchase",
            scope="family",
        ),
        Transaction(
            family=family,
            account=account,
            occurred_at=datetime(2026, 5, 3, 11, 0),
            amount=Decimal("-200.00"),
            currency="UAH",
            direction="expense",
            flow_type="purchase",
            scope="work_fop",
        ),
        Transaction(
            family=family,
            account=account,
            occurred_at=datetime(2026, 5, 3, 12, 0),
            amount=Decimal("-500.00"),
            currency="UAH",
            direction="expense",
            flow_type="person_transfer",
            scope="family",
        ),
        Transaction(
            family=family,
            account=account,
            occurred_at=datetime(2026, 5, 4, 12, 0),
            amount=Decimal("-900.00"),
            currency="UAH",
            direction="expense",
            flow_type="transfer_to_savings",
            scope="family",
            deleted_at=datetime(2026, 5, 4, 13, 0),
        ),
    ]
    db_session.add_all([family, user, account, cash_account, *transactions])
    db_session.commit()
    return family, account
