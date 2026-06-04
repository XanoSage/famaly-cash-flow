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


def test_get_analytics_work_fop(client: TestClient, db_session: Session) -> None:
    family = _seed_transactions(db_session)

    response = client.get(
        "/api/v1/analytics/work-fop",
        params={"family_id": str(family.id)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["income"] == "3000.00"
    assert payload["summary"]["expenses"] == "700.00"
    assert payload["summary"]["net_cash_flow"] == "2300.00"
    assert payload["summary"]["transaction_count"] == 3
    assert payload["timeline"]["rows"][0]["income"] == "3000.00"
    assert payload["timeline"]["rows"][1]["expenses"] == "700.00"
    assert payload["top_categories"]["total_amount"] == "700.00"
    assert payload["top_categories"]["rows"][0]["category_name"] == "Software"
    assert payload["top_merchants"]["rows"][0]["merchant_name"] == "GitHub"


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
    category = Category(family=family, name="Software", is_system=False)
    merchant = Merchant(
        family=family,
        name="GitHub",
        normalized_name="github",
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
                amount=Decimal("3000.00"),
                currency="UAH",
                direction="income",
                flow_type="income",
                scope="work_fop",
            ),
            Transaction(
                family=family,
                account=account,
                category=category,
                merchant=merchant,
                occurred_at=datetime(2026, 5, 2, 10, 0),
                amount=Decimal("-500.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="work_fop",
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
            ),
            Transaction(
                family=family,
                account=account,
                category=category,
                merchant=merchant,
                occurred_at=datetime(2026, 5, 2, 12, 0),
                amount=Decimal("-1000.00"),
                currency="UAH",
                direction="expense",
                flow_type="purchase",
                scope="family",
            ),
        ]
    )
    db_session.commit()
    return family
