from collections.abc import Generator

import pytest
from auth_helpers import current_test_user_dependency
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.auth.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.account import Account
from app.models.family import Family
from app.models.user import User, UserPreference


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
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = current_test_user_dependency(db_session)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_list_accounts_returns_active_accounts_for_current_family_and_marks_default(
    api_client: TestClient,
    db_session: Session,
) -> None:
    family = Family(name="Family A")
    other_family = Family(name="Family B")
    user = User(
        family=family,
        email="account-owner@example.com",
        password_hash="test-hash",
        display_name="Account Owner",
    )
    default_account = Account(
        family=family,
        owner_user=user,
        type="bank",
        name="Main card",
        currency="UAH",
        is_active=True,
    )
    other_account = Account(
        family=family,
        type="bank",
        name="Savings",
        currency="EUR",
        is_active=True,
    )
    inactive_account = Account(
        family=family,
        type="bank",
        name="Closed account",
        currency="UAH",
        is_active=False,
    )
    foreign_account = Account(
        family=other_family,
        type="bank",
        name="Family B private account",
        currency="USD",
        is_active=True,
    )
    preference = UserPreference(user=user, default_account=default_account, language="uk")
    db_session.add_all(
        [
            family,
            other_family,
            user,
            default_account,
            other_account,
            inactive_account,
            foreign_account,
            preference,
        ]
    )
    db_session.commit()

    response = api_client.get("/api/v1/accounts", params={"family_id": str(other_family.id)})

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert [row["name"] for row in rows] == ["Main card", "Savings"]
    assert {row["name"] for row in rows}.isdisjoint({"Closed account", "Family B private account"})
    assert rows[0]["is_default"] is True
    assert rows[1]["is_default"] is False
    assert rows[0]["owner_user_id"] == str(user.id)


def test_list_accounts_requires_authentication(
    api_client: TestClient,
) -> None:
    api_client.app.dependency_overrides.pop(get_current_user, None)
    response = api_client.get("/api/v1/accounts")
    assert response.status_code == 401
