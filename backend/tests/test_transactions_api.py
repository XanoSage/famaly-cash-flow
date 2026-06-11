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


def test_list_transactions_returns_family_transactions_ordered(
    client: TestClient,
    db_session: Session,
) -> None:
    family, account, _, merchant = _seed_transactions(db_session)

    response = client.get(
        "/api/v1/transactions",
        params={"family_id": str(family.id), "limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["offset"] == 0
    assert payload["limit"] == 10
    assert [row["description_raw"] for row in payload["rows"]] == [
        "Сільпо",
        "Переказ на картку",
        "Скарбничка",
    ]
    assert payload["rows"][0]["account_id"] == str(account.id)
    assert payload["rows"][0]["merchant_id"] == str(merchant.id)
    assert payload["rows"][0]["category_name"] == "Food"
    assert payload["rows"][0]["merchant_name"] == "Сільпо"


def test_list_transactions_filters_by_flow_type_and_review(
    client: TestClient,
    db_session: Session,
) -> None:
    family, _, _, _ = _seed_transactions(db_session)

    response = client.get(
        "/api/v1/transactions",
        params={
            "family_id": str(family.id),
            "flow_type": "person_transfer",
            "needs_review": "true",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["rows"][0]["flow_type"] == "person_transfer"
    assert payload["rows"][0]["needs_review"] is True


def test_list_transactions_hides_deleted_by_default(
    client: TestClient,
    db_session: Session,
) -> None:
    family, _, deleted_transaction, _ = _seed_transactions(db_session)
    deleted_transaction.deleted_at = datetime(2026, 5, 9)
    db_session.commit()

    default_response = client.get(
        "/api/v1/transactions",
        params={"family_id": str(family.id)},
    )
    include_deleted_response = client.get(
        "/api/v1/transactions",
        params={"family_id": str(family.id), "include_deleted": "true"},
    )

    assert default_response.status_code == 200
    assert default_response.json()["total"] == 2
    assert include_deleted_response.status_code == 200
    assert include_deleted_response.json()["total"] == 3


def test_list_transactions_filters_by_date_range(client: TestClient, db_session: Session) -> None:
    family, _, _, _ = _seed_transactions(db_session)

    response = client.get(
        "/api/v1/transactions",
        params={
            "family_id": str(family.id),
            "occurred_from": "2026-05-08T10:00:00",
            "occurred_to": "2026-05-08T16:00:00",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert {row["description_raw"] for row in payload["rows"]} == {"Сільпо", "Переказ на картку"}


def _seed_transactions(db_session: Session) -> tuple[Family, Account, Transaction, Merchant]:
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
    merchant = Merchant(
        family=family,
        name="Сільпо",
        normalized_name="сільпо",
        merchant_type="store",
    )
    category = Category(
        family=family,
        name="Food",
        is_system=False,
    )
    supermarket = Transaction(
        family=family,
        account=account,
        owner_user=user,
        occurred_at=datetime(2026, 5, 8, 15, 25),
        amount=Decimal("-118.02"),
        currency="UAH",
        direction="expense",
        flow_type="purchase",
        scope="family",
        description_raw="Сільпо",
        description_normalized="сільпо",
        merchant=merchant,
        category=category,
        needs_review=False,
    )
    transfer = Transaction(
        family=family,
        account=account,
        owner_user=user,
        occurred_at=datetime(2026, 5, 8, 10, 0),
        amount=Decimal("-700.00"),
        currency="UAH",
        direction="expense",
        flow_type="person_transfer",
        scope="family",
        description_raw="Переказ на картку",
        description_normalized="переказ на картку",
        needs_review=True,
    )
    savings = Transaction(
        family=family,
        account=account,
        owner_user=user,
        occurred_at=datetime(2026, 5, 7, 18, 0),
        amount=Decimal("-9.20"),
        currency="UAH",
        direction="expense",
        flow_type="transfer_to_savings",
        scope="family",
        description_raw="Скарбничка",
        description_normalized="скарбничка",
        needs_review=False,
    )
    db_session.add_all([family, user, account, merchant, category, supermarket, transfer, savings])
    db_session.commit()
    return family, account, savings, merchant
