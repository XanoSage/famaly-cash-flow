from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.analytics.work_fop import WorkFopAnalyticsService
from app.db.base import Base
from app.models.account import Account
from app.models.category import Category
from app.models.family import Family
from app.models.merchant import Merchant
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


def test_work_fop_analytics_uses_only_work_scope(db_session: Session) -> None:
    family, _ = _seed_work_fop_transactions(db_session)

    analytics = WorkFopAnalyticsService(db_session).build(family_id=family.id)

    assert analytics.summary.income == Decimal("2000.00")
    assert analytics.summary.expenses == Decimal("500.00")
    assert analytics.summary.savings == Decimal("0.00")
    assert analytics.summary.net_cash_flow == Decimal("1500.00")
    assert analytics.summary.transaction_count == 3
    assert analytics.summary.work_fop_count == 3

    assert [row.period.isoformat() for row in analytics.timeline.rows] == ["2026-05-01", "2026-05-02"]
    assert analytics.timeline.rows[0].income == Decimal("2000.00")
    assert analytics.timeline.rows[1].expenses == Decimal("500.00")

    assert analytics.top_categories.total_amount == Decimal("500.00")
    assert analytics.top_categories.rows[0].category_name == "Work services"
    assert analytics.top_merchants.total_amount == Decimal("500.00")
    assert analytics.top_merchants.rows[0].merchant_name == "OpenAI"


def test_work_fop_analytics_filters_by_account(db_session: Session) -> None:
    family, account = _seed_work_fop_transactions(db_session)

    analytics = WorkFopAnalyticsService(db_session).build(
        family_id=family.id,
        account_id=account.id,
    )

    assert analytics.summary.transaction_count == 3
    assert analytics.summary.expenses == Decimal("500.00")


def _seed_work_fop_transactions(db_session: Session) -> tuple[Family, Account]:
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
    category = Category(family=family, name="Work services", is_system=False)
    merchant = Merchant(
        family=family,
        name="OpenAI",
        normalized_name="openai",
        merchant_type="service",
    )
    db_session.add_all(
        [
            family,
            user,
            account,
            category,
            merchant,
            Transaction(
                family=family,
                account=account,
                occurred_at=datetime(2026, 5, 1, 9, 0),
                amount=Decimal("2000.00"),
                currency="UAH",
                direction="income",
                flow_type="income",
                scope="work_fop",
                description_raw="Client payment",
            ),
            Transaction(
                family=family,
                account=account,
                category=category,
                merchant=merchant,
                occurred_at=datetime(2026, 5, 2, 10, 0),
                amount=Decimal("-300.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="work_fop",
                description_raw="OpenAI",
            ),
            Transaction(
                family=family,
                account=account,
                category=category,
                merchant=merchant,
                occurred_at=datetime(2026, 5, 2, 11, 0),
                amount=Decimal("-200.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="work_fop",
                description_raw="OpenAI",
            ),
            Transaction(
                family=family,
                account=account,
                category=category,
                merchant=merchant,
                occurred_at=datetime(2026, 5, 2, 12, 0),
                amount=Decimal("-900.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
                description_raw="Family should be ignored",
            ),
        ]
    )
    db_session.commit()
    return family, account
