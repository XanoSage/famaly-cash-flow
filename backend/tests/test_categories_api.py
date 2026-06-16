from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.category import Category, Subcategory
from app.models.family import Family


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


def test_list_categories_returns_system_and_family_categories(
    client: TestClient,
    db_session: Session,
) -> None:
    family = Family(name="Family")
    other_family = Family(name="Other")
    system_category = Category(
        family_id=None,
        name="Food",
        translation_key="categories.food",
        is_system=True,
    )
    system_subcategory = Subcategory(
        category=system_category,
        name="Groceries",
        translation_key="categories.groceries",
        is_system=True,
    )
    family_category = Category(family=family, name="Kids", is_system=False)
    other_category = Category(family=other_family, name="Other private", is_system=False)
    db_session.add_all(
        [family, other_family, system_category, system_subcategory, family_category, other_category]
    )
    db_session.commit()

    response = client.get("/api/v1/categories", params={"family_id": str(family.id)})

    assert response.status_code == 200
    payload = response.json()
    assert [row["name"] for row in payload["rows"]] == ["Food", "Kids"]
    assert payload["rows"][0]["family_id"] is None
    assert payload["rows"][0]["subcategories"][0]["name"] == "Groceries"
