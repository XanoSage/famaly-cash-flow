from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.analytics.merchants import MerchantAnalyticsService
from app.db.base import Base
from app.models.account import Account
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


def test_merchant_analytics_groups_expenses_by_merchant(db_session: Session) -> None:
    family, _, silpo, atb = _seed_merchant_transactions(db_session)

    analytics = MerchantAnalyticsService(db_session).build(family_id=family.id)

    assert analytics.total_amount == Decimal("420.00")
    assert analytics.total_transactions == 3
    assert [row.merchant_name for row in analytics.rows] == ["Сільпо", "АТБ"]
    assert analytics.rows[0].merchant_id == silpo.id
    assert analytics.rows[0].amount == Decimal("300.00")
    assert analytics.rows[0].transaction_count == 2
    assert analytics.rows[0].share_percent == Decimal("71.43")
    assert analytics.rows[1].merchant_id == atb.id
    assert analytics.rows[1].amount == Decimal("120.00")


def test_merchant_analytics_can_sort_by_count(db_session: Session) -> None:
    family, _, _, _ = _seed_merchant_transactions(db_session)

    analytics = MerchantAnalyticsService(db_session).build(family_id=family.id, sort_by="count")

    assert [row.merchant_name for row in analytics.rows] == ["Сільпо", "АТБ"]


def test_merchant_analytics_filters_by_scope_and_period(db_session: Session) -> None:
    family, _, _, _ = _seed_merchant_transactions(db_session)

    analytics = MerchantAnalyticsService(db_session).build(
        family_id=family.id,
        occurred_from=datetime(2026, 5, 2),
        occurred_to=datetime(2026, 5, 2, 23, 59),
        scope="family",
    )

    assert analytics.total_amount == Decimal("200.00")
    assert analytics.total_transactions == 1
    assert analytics.rows[0].merchant_name == "Сільпо"


def _seed_merchant_transactions(db_session: Session) -> tuple[Family, Account, Merchant, Merchant]:
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
    silpo = Merchant(
        family=family,
        name="Сільпо",
        normalized_name="сільпо",
        merchant_type="store",
    )
    atb = Merchant(
        family=family,
        name="АТБ",
        normalized_name="атб",
        merchant_type="store",
    )
    db_session.add_all(
        [
            family,
            user,
            account,
            silpo,
            atb,
            Transaction(
                family=family,
                account=account,
                merchant=silpo,
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
                merchant=silpo,
                occurred_at=datetime(2026, 5, 2, 10, 0),
                amount=Decimal("-200.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
                description_raw="Сільпо",
            ),
            Transaction(
                family=family,
                account=account,
                merchant=atb,
                occurred_at=datetime(2026, 5, 3, 10, 0),
                amount=Decimal("-120.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
                description_raw="АТБ",
            ),
            Transaction(
                family=family,
                account=account,
                merchant=silpo,
                occurred_at=datetime(2026, 5, 4, 10, 0),
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
                merchant=atb,
                occurred_at=datetime(2026, 5, 5, 10, 0),
                amount=Decimal("-500.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="work_fop",
                description_raw="АТБ work",
                deleted_at=datetime(2026, 5, 6),
            ),
        ]
    )
    db_session.commit()
    return family, account, silpo, atb
