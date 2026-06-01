from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.analytics.categories import CategoryAnalyticsService
from app.db.base import Base
from app.models.account import Account
from app.models.category import Category, Subcategory
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


def test_category_analytics_groups_expenses_by_category(db_session: Session) -> None:
    family, food, health, _ = _seed_category_transactions(db_session)

    analytics = CategoryAnalyticsService(db_session).build(family_id=family.id)

    assert analytics.total_amount == Decimal("530.00")
    assert analytics.total_transactions == 4
    assert [row.category_name for row in analytics.rows] == ["Еда", "Здоровье", "Uncategorized"]
    assert analytics.rows[0].category_id == food.id
    assert analytics.rows[0].amount == Decimal("300.00")
    assert analytics.rows[0].transaction_count == 2
    assert analytics.rows[0].share_percent == Decimal("56.60")
    assert analytics.rows[1].category_id == health.id
    assert analytics.rows[1].amount == Decimal("180.00")


def test_category_analytics_can_include_subcategories(db_session: Session) -> None:
    family, _, _, supermarket = _seed_category_transactions(db_session)

    analytics = CategoryAnalyticsService(db_session).build(
        family_id=family.id,
        include_subcategories=True,
    )

    assert analytics.rows[0].subcategory_id == supermarket.id
    assert analytics.rows[0].subcategory_name == "Супермаркеты"


def test_category_analytics_filters_by_scope_and_period(db_session: Session) -> None:
    family, _, _, _ = _seed_category_transactions(db_session)

    analytics = CategoryAnalyticsService(db_session).build(
        family_id=family.id,
        occurred_from=datetime(2026, 5, 3),
        occurred_to=datetime(2026, 5, 3, 23, 59),
        scope="family",
    )

    assert analytics.total_amount == Decimal("180.00")
    assert analytics.total_transactions == 1
    assert analytics.rows[0].category_name == "Здоровье"


def _seed_category_transactions(db_session: Session) -> tuple[Family, Category, Category, Subcategory]:
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
    food = Category(family=family, name="Еда", is_system=False)
    health = Category(family=family, name="Здоровье", is_system=False)
    supermarket = Subcategory(category=food, name="Супермаркеты", is_system=False)
    db_session.add_all(
        [
            family,
            user,
            account,
            food,
            health,
            supermarket,
            Transaction(
                family=family,
                account=account,
                category=food,
                subcategory=supermarket,
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
                category=food,
                subcategory=supermarket,
                occurred_at=datetime(2026, 5, 2, 10, 0),
                amount=Decimal("-200.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
                description_raw="АТБ",
            ),
            Transaction(
                family=family,
                account=account,
                category=health,
                occurred_at=datetime(2026, 5, 3, 10, 0),
                amount=Decimal("-180.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
                description_raw="Аптека",
            ),
            Transaction(
                family=family,
                account=account,
                occurred_at=datetime(2026, 5, 4, 10, 0),
                amount=Decimal("-50.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
                description_raw="Нужно разобрать",
            ),
            Transaction(
                family=family,
                account=account,
                category=food,
                occurred_at=datetime(2026, 5, 5, 10, 0),
                amount=Decimal("-70.00"),
                currency="UAH",
                direction="expense",
                flow_type="transfer_to_savings",
                scope="family",
                description_raw="Скарбничка",
            ),
            Transaction(
                family=family,
                account=account,
                category=health,
                occurred_at=datetime(2026, 5, 6, 10, 0),
                amount=Decimal("-500.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="work_fop",
                deleted_at=datetime(2026, 5, 7),
                description_raw="Deleted work",
            ),
        ]
    )
    db_session.commit()
    return family, food, health, supermarket
