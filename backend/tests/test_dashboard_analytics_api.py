from collections.abc import Generator
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.account import Account
from app.models.category import Category
from app.models.family import Family
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.models.user import User


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


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_get_analytics_dashboard(client: TestClient, db_session: Session) -> None:
    family = _seed_transactions(db_session)

    response = client.get(
        "/api/v1/analytics/dashboard",
        params={
            "family_id": str(family.id),
            "category_limit": 1,
            "merchant_limit": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["summary"]["income"] == "1000.00"
    assert payload["summary"]["expenses"] == "380.00"
    assert payload["summary"]["savings"] == "50.00"
    assert payload["summary"]["transfers"] == "200.00"
    assert payload["summary"]["net_cash_flow"] == "570.00"

    assert payload["timeline"]["granularity"] == "day"
    assert [row["period"] for row in payload["timeline"]["rows"]] == ["2026-05-01", "2026-05-02"]
    assert payload["timeline"]["rows"][0]["expenses"] == "100.00"
    assert payload["timeline"]["rows"][1]["expenses"] == "280.00"
    assert payload["timeline"]["rows"][1]["transfers"] == "200.00"

    assert payload["top_categories"]["total_amount"] == "380.00"
    assert len(payload["top_categories"]["rows"]) == 1
    assert payload["top_categories"]["rows"][0]["category_name"] == "Food"
    assert payload["top_categories"]["rows"][0]["amount"] == "300.00"

    assert payload["top_merchants"]["total_amount"] == "380.00"
    assert len(payload["top_merchants"]["rows"]) == 1
    assert payload["top_merchants"]["rows"][0]["merchant_name"] == "Silpo"
    assert payload["top_merchants"]["rows"][0]["amount"] == "300.00"


def test_get_analytics_dashboard_filters_by_scope(client: TestClient, db_session: Session) -> None:
    family = _seed_transactions(db_session)

    response = client.get(
        "/api/v1/analytics/dashboard",
        params={
            "family_id": str(family.id),
            "scope": "family",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["expenses"] == "300.00"
    assert payload["summary"]["net_cash_flow"] == "650.00"
    assert payload["top_categories"]["total_amount"] == "300.00"
    assert payload["top_merchants"]["total_amount"] == "300.00"
    assert payload["timeline"]["rows"][1]["expenses"] == "200.00"


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
    health = Category(family=family, name="Health", is_system=False)
    silpo = Merchant(
        family=family,
        name="Silpo",
        normalized_name="silpo",
        merchant_type="store",
    )
    pharmacy = Merchant(
        family=family,
        name="Pharmacy",
        normalized_name="pharmacy",
        merchant_type="store",
    )
    db_session.add_all(
        [
            family,
            user,
            account,
            food,
            health,
            silpo,
            pharmacy,
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
                amount=Decimal("-100.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
            ),
            Transaction(
                family=family,
                account=account,
                category=food,
                merchant=silpo,
                occurred_at=datetime(2026, 5, 2, 10, 0),
                amount=Decimal("-200.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
            ),
            Transaction(
                family=family,
                account=account,
                category=health,
                merchant=pharmacy,
                occurred_at=datetime(2026, 5, 2, 11, 0),
                amount=Decimal("-80.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="work_fop",
            ),
            Transaction(
                family=family,
                account=account,
                occurred_at=datetime(2026, 5, 2, 12, 0),
                amount=Decimal("-50.00"),
                currency="UAH",
                direction="expense",
                flow_type="transfer_to_savings",
                scope="family",
            ),
            Transaction(
                family=family,
                account=account,
                occurred_at=datetime(2026, 5, 2, 13, 0),
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
