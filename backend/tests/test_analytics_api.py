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
from app.models.family import Family
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


def test_get_analytics_summary(client: TestClient, db_session: Session) -> None:
    family = _seed_transactions(db_session)

    response = client.get(
        "/api/v1/analytics/summary",
        params={"family_id": str(family.id)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["income"] == "1000.00"
    assert payload["expenses"] == "100.00"
    assert payload["savings"] == "50.00"
    assert payload["transfers"] == "200.00"
    assert payload["net_cash_flow"] == "850.00"
    assert payload["transaction_count"] == 4


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
    db_session.add_all(
        [
            family,
            user,
            account,
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
                occurred_at=datetime(2026, 5, 2, 10, 0),
                amount=Decimal("-50.00"),
                currency="UAH",
                direction="expense",
                flow_type="transfer_to_savings",
                scope="family",
            ),
            Transaction(
                family=family,
                account=account,
                occurred_at=datetime(2026, 5, 3, 10, 0),
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
