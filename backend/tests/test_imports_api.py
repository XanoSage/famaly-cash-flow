from collections.abc import Generator
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.account import Account
from app.models.family import Family
from app.models.import_batch import ImportBatch
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


def test_create_import_preview_uploads_xlsx(client: TestClient, db_session: Session) -> None:
    family, user = _create_family_and_user(db_session)

    response = client.post(
        "/api/v1/imports/preview",
        params={
            "family_id": str(family.id),
            "uploaded_by_user_id": str(user.id),
            "preview_limit": 1,
        },
        files={
            "file": (
                "statement.xlsx",
                _make_statement_xlsx(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["summary"]["source_filename"] == "statement.xlsx"
    assert payload["summary"]["status"] == "draft"
    assert payload["summary"]["total_rows"] == 2
    assert payload["summary"]["returned_rows"] == 1
    assert payload["summary"]["offset"] == 0
    assert payload["summary"]["limit"] == 1
    assert payload["summary"]["auto_ready_count"] == 1
    assert payload["summary"]["needs_review_count"] == 1
    assert payload["rows"][0]["merchant_name"] == "Сільпо"

    assert db_session.query(ImportBatch).count() == 1


def test_get_import_preview_reopens_saved_draft(client: TestClient, db_session: Session) -> None:
    family, user = _create_family_and_user(db_session)
    upload_response = _upload_statement_preview(client, family, user)
    import_batch_id = upload_response.json()["summary"]["import_batch_id"]

    response = client.get(
        f"/api/v1/imports/{import_batch_id}/preview",
        params={
            "family_id": str(family.id),
            "offset": 1,
            "limit": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["import_batch_id"] == import_batch_id
    assert payload["summary"]["total_rows"] == 2
    assert payload["summary"]["returned_rows"] == 1
    assert payload["summary"]["offset"] == 1
    assert payload["summary"]["limit"] == 1
    assert payload["rows"][0]["row_number"] == 4


def test_get_import_preview_filters_by_status(client: TestClient, db_session: Session) -> None:
    family, user = _create_family_and_user(db_session)
    upload_response = _upload_statement_preview(client, family, user)
    import_batch_id = upload_response.json()["summary"]["import_batch_id"]

    response = client.get(
        f"/api/v1/imports/{import_batch_id}/preview",
        params={
            "family_id": str(family.id),
            "row_status": "needs_review",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["returned_rows"] == 1
    assert payload["summary"]["auto_ready_count"] == 1
    assert payload["summary"]["needs_review_count"] == 1
    assert payload["rows"][0]["status"] == "needs_review"
    assert payload["rows"][0]["reason_codes"] == ["person_transfer"]


def test_get_import_preview_returns_404_for_other_family(
    client: TestClient,
    db_session: Session,
) -> None:
    family, user = _create_family_and_user(db_session)
    other_family = Family(name="Other")
    db_session.add(other_family)
    db_session.commit()
    upload_response = _upload_statement_preview(client, family, user)
    import_batch_id = upload_response.json()["summary"]["import_batch_id"]

    response = client.get(
        f"/api/v1/imports/{import_batch_id}/preview",
        params={"family_id": str(other_family.id)},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Import preview not found."


def test_confirm_import_preview_creates_transactions(client: TestClient, db_session: Session) -> None:
    family, user = _create_family_and_user(db_session)
    account = _create_account(db_session, family, user)
    upload_response = _upload_statement_preview(client, family, user)
    import_batch_id = upload_response.json()["summary"]["import_batch_id"]

    response = client.post(
        f"/api/v1/imports/{import_batch_id}/confirm",
        params={
            "family_id": str(family.id),
            "account_id": str(account.id),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["import_batch_id"] == import_batch_id
    assert payload["status"] == "confirmed"
    assert payload["created_transactions"] == 2
    assert db_session.query(Transaction).count() == 2


def test_create_import_preview_rejects_non_xlsx(client: TestClient, db_session: Session) -> None:
    family, user = _create_family_and_user(db_session)

    response = client.post(
        "/api/v1/imports/preview",
        params={
            "family_id": str(family.id),
            "uploaded_by_user_id": str(user.id),
        },
        files={"file": ("statement.txt", b"not xlsx", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only .xlsx files are supported."


def test_create_import_preview_rejects_user_from_other_family(
    client: TestClient,
    db_session: Session,
) -> None:
    target_family = Family(name="Target")
    other_family = Family(name="Other")
    user = User(
        family=other_family,
        email="owner@example.com",
        password_hash="hash",
        display_name="Owner",
    )
    db_session.add_all([target_family, other_family, user])
    db_session.commit()

    response = client.post(
        "/api/v1/imports/preview",
        params={
            "family_id": str(target_family.id),
            "uploaded_by_user_id": str(user.id),
        },
        files={
            "file": (
                "statement.xlsx",
                _make_statement_xlsx(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploader does not belong to the target family."


def _create_family_and_user(db_session: Session) -> tuple[Family, User]:
    family = Family(name="Test Family")
    user = User(
        family=family,
        email="owner@example.com",
        password_hash="hash",
        display_name="Owner",
    )
    db_session.add_all([family, user])
    db_session.commit()
    return family, user


def _create_account(db_session: Session, family: Family, user: User) -> Account:
    account = Account(
        family=family,
        owner_user=user,
        type="card",
        name="Main card",
        currency="UAH",
    )
    db_session.add(account)
    db_session.commit()
    return account


def _upload_statement_preview(client: TestClient, family: Family, user: User):
    return client.post(
        "/api/v1/imports/preview",
        params={
            "family_id": str(family.id),
            "uploaded_by_user_id": str(user.id),
        },
        files={
            "file": (
                "statement.xlsx",
                _make_statement_xlsx(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )


def _make_statement_xlsx() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Виписки"
    worksheet.append(["Історія операцій за період 08.02.2026 - 08.05.2026"])
    worksheet.append(
        [
            "Дата",
            "Категорія",
            "Картка",
            "Опис операції",
            "Сума в валюті картки",
            "Валюта картки",
            "Сума в валюті транзакції",
            "Валюта транзакції",
            "Залишок на кінець періоду",
            "Валюта залишку",
        ]
    )
    worksheet.append(
        [
            "08.05.2026 15:25:00",
            "Супермаркети та продукти",
            "4627 **** **** 3421",
            "Сільпо",
            -118.02,
            "UAH",
            118.02,
            "UAH",
            6248.97,
            "UAH",
        ]
    )
    worksheet.append(
        [
            "08.05.2026 10:00:00",
            "Перекази",
            "4627 **** **** 3421",
            "Переказ на картку",
            -700,
            "UAH",
            700,
            "UAH",
            1000,
            "UAH",
        ]
    )
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
