from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.analytics.insights import AnalyticsInsightsService
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


def test_insights_builds_fact_based_recommendations(db_session: Session) -> None:
    family = _seed_transactions(db_session)

    insights = AnalyticsInsightsService(db_session).build(family_id=family.id)

    codes = [row.code for row in insights.rows]
    assert codes == [
        "negative_cash_flow",
        "needs_review",
        "uncategorized_expenses",
        "top_category",
        "top_merchants",
        "savings_progress",
        "average_daily_expense",
    ]
    assert insights.rows[0].severity == "warning"
    assert insights.rows[0].metric_value == Decimal("-150.00")
    assert insights.rows[3].metric_name == "top_category_amount"
    assert insights.rows[3].metric_value == Decimal("800.00")
    assert insights.rows[5].severity == "positive"


def test_insights_returns_no_data_message(db_session: Session) -> None:
    family = Family(name="Empty Family")
    db_session.add(family)
    db_session.commit()

    insights = AnalyticsInsightsService(db_session).build(family_id=family.id)

    assert len(insights.rows) == 1
    assert insights.rows[0].code == "no_transactions"
    assert insights.rows[0].metric_value == Decimal("0.00")


def _seed_transactions(db_session: Session) -> Family:
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
    food = Category(family=family, name="Food", is_system=False)
    silpo = Merchant(
        family=family,
        name="Silpo",
        normalized_name="silpo",
        merchant_type="store",
    )
    db_session.add_all(
        [
            family,
            user,
            account,
            food,
            silpo,
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
                category=food,
                merchant=silpo,
                occurred_at=datetime(2026, 5, 1, 10, 0),
                amount=Decimal("-800.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
            ),
            Transaction(
                family=family,
                account=account,
                occurred_at=datetime(2026, 5, 2, 10, 0),
                amount=Decimal("-300.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
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
            ),
        ]
    )
    db_session.commit()
    return family
