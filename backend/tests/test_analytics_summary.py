from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.analytics.summary import AnalyticsSummaryService
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


def test_analytics_summary_separates_expenses_savings_and_transfers(
    db_session: Session,
) -> None:
    family, account = _seed_summary_transactions(db_session)

    summary = AnalyticsSummaryService(db_session).build(family_id=family.id)

    assert summary.income == Decimal("1000.00")
    assert summary.expenses == Decimal("300.00")
    assert summary.savings == Decimal("50.00")
    assert summary.transfers == Decimal("200.00")
    assert summary.net_cash_flow == Decimal("650.00")
    assert summary.average_daily_expense == Decimal("150.00")
    assert summary.transaction_count == 5
    assert summary.expense_count == 2
    assert summary.income_count == 1
    assert summary.savings_count == 1
    assert summary.transfer_count == 1
    assert summary.needs_review_count == 1
    assert summary.uncategorized_count == 2
    assert summary.work_fop_count == 1

    account_summary = AnalyticsSummaryService(db_session).build(
        family_id=family.id,
        account_id=account.id,
    )
    assert account_summary.transaction_count == 5


def test_analytics_summary_filters_by_period_and_scope(db_session: Session) -> None:
    family, _ = _seed_summary_transactions(db_session)

    summary = AnalyticsSummaryService(db_session).build(
        family_id=family.id,
        occurred_from=datetime(2026, 5, 2),
        occurred_to=datetime(2026, 5, 3, 23, 59),
        scope="work_fop",
    )

    assert summary.transaction_count == 1
    assert summary.expenses == Decimal("200.00")
    assert summary.savings == Decimal("0.00")
    assert summary.income == Decimal("0.00")


def _seed_summary_transactions(db_session: Session) -> tuple[Family, Account]:
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
            amount=Decimal("-100.00"),
            currency="UAH",
            direction="expense",
            flow_type="purchase",
            scope="family",
            description_raw="Сільпо",
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
            description_raw="GitHub",
            needs_review=True,
        ),
        Transaction(
            family=family,
            account=account,
            occurred_at=datetime(2026, 5, 3, 10, 0),
            amount=Decimal("-50.00"),
            currency="UAH",
            direction="expense",
            flow_type="transfer_to_savings",
            scope="family",
            description_raw="Скарбничка",
        ),
        Transaction(
            family=family,
            account=account,
            occurred_at=datetime(2026, 5, 4, 10, 0),
            amount=Decimal("-200.00"),
            currency="UAH",
            direction="expense",
            flow_type="person_transfer",
            scope="family",
            description_raw="Переказ",
        ),
    ]
    db_session.add_all([family, user, account, *transactions])
    db_session.commit()
    return family, account
