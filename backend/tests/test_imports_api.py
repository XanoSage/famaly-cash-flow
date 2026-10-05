from collections.abc import Generator
from datetime import datetime
from decimal import Decimal
from io import BytesIO

import pytest
from auth_helpers import current_test_user_dependency
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.auth.dependencies import get_current_user
from app.db.base import Base
from app.db.seed_system_categories import seed_system_categories
from app.db.session import get_db
from app.importers.bank_xlsx import (
    BankStatementParseResult,
    BankStatementSummary,
    ParsedBankOperation,
)
from app.main import app
from app.models.account import Account
from app.models.category import Category
from app.models.family import Family
from app.models.import_batch import ImportBatch
from app.models.transaction import Transaction
from app.models.user import User
from app.services.import_preview import ImportPreviewService


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
        seed_system_categories(session)
        yield session


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = current_test_user_dependency(db_session)
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
    assert payload["rows"][0]["reason_codes"] == ["person_transfer", "uncategorized"]


def test_get_import_preview_uses_authenticated_family_instead_of_query_parameter(
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

    assert response.status_code == 200
    assert response.json()["summary"]["import_batch_id"] == import_batch_id


def test_confirm_import_preview_creates_transactions(
    client: TestClient, db_session: Session
) -> None:
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


def test_row_patch_and_bulk_actions_return_reviewed_contract(
    client: TestClient, db_session: Session
) -> None:
    family, user = _create_family_and_user(db_session)
    category = db_session.scalar(
        select(Category).where(Category.family_id.is_(None), Category.name == "Дом")
    )
    assert category is not None
    uploaded = _upload_statement_preview(client, family, user)
    batch_id = uploaded.json()["summary"]["import_batch_id"]
    row_id = uploaded.json()["rows"][0]["id"]

    patched = client.patch(
        f"/api/v1/imports/{batch_id}/preview/{row_id}",
        json={"proposed_category_id": str(category.id), "save_rule": True},
    )
    assert patched.status_code == 200
    row = patched.json()["rows"][0]
    assert row["proposed_category_id"] == str(category.id)
    assert row["proposed_category_name"] == "Дом"
    assert row["status"] == "auto_ready"
    assert patched.json()["summary"]["uncategorized_count"] == 1

    bulk = client.post(
        f"/api/v1/imports/{batch_id}/bulk-actions",
        json={"action": "exclude", "row_ids": [row_id]},
    )
    assert bulk.status_code == 200
    assert bulk.json()["rows"][0]["status"] == "excluded"
    assert bulk.json()["summary"]["excluded_count"] == 1


def test_import_review_endpoints_reject_foreign_families_and_entities(
    client: TestClient, db_session: Session
) -> None:
    family_a, user_a = _create_family_and_user(db_session)
    family_b = Family(name="Other Family")
    user_b = User(
        family=family_b,
        email="other@example.com",
        password_hash="hash",
        display_name="Other",
    )
    foreign_category = Category(family=family_b, name="Private category", is_system=False)
    db_session.add_all([family_b, user_b, foreign_category])
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_a

    own_preview = _upload_statement_preview(client, family_a, user_a).json()
    own_batch_id = own_preview["summary"]["import_batch_id"]
    own_row_id = own_preview["rows"][0]["id"]
    foreign_batch = _create_foreign_preview(db_session, family_b, user_b)
    foreign_row = db_session.scalar(select(ImportBatch).where(ImportBatch.id == foreign_batch.id))
    assert foreign_row is not None
    foreign_row_id = foreign_row.preview_rows[0].id

    fetch = client.get(f"/api/v1/imports/{foreign_batch.id}/preview")
    assert fetch.status_code == 404
    patch_foreign_row = client.patch(
        f"/api/v1/imports/{own_batch_id}/preview/{foreign_row_id}",
        json={"excluded": True},
    )
    assert patch_foreign_row.status_code == 400
    bulk_foreign_row = client.post(
        f"/api/v1/imports/{own_batch_id}/bulk-actions",
        json={"action": "exclude", "row_ids": [str(foreign_row_id)]},
    )
    assert bulk_foreign_row.status_code == 400
    foreign_category = client.patch(
        f"/api/v1/imports/{own_batch_id}/preview/{own_row_id}",
        json={"proposed_category_id": str(foreign_category.id)},
    )
    assert foreign_category.status_code == 400


def test_duplicate_matching_and_metadata_are_family_scoped(
    client: TestClient, db_session: Session
) -> None:
    family_a, user_a = _create_family_and_user(db_session)
    family_b = Family(name="Transaction Family")
    user_b = User(
        family=family_b,
        email="transaction-family@example.com",
        password_hash="hash",
        display_name="Other",
    )
    account_b = Account(
        family=family_b,
        owner_user=user_b,
        type="card",
        name="Foreign account",
        currency="UAH",
    )
    foreign_transaction = Transaction(
        family=family_b,
        account=account_b,
        occurred_at=datetime(2026, 5, 8, 15, 25),
        amount=Decimal("-118.02"),
        currency="UAH",
        direction="expense",
        flow_type="purchase",
        scope="family",
        description_raw="Сільпо",
        description_normalized="сільпо",
    )
    db_session.add_all([family_b, user_b, account_b, foreign_transaction])
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_a

    response = _upload_statement_preview(client, family_a, user_a)

    assert response.status_code == 201
    row = response.json()["rows"][0]
    assert row["status"] == "auto_ready"
    assert row["duplicate_transaction_id"] is None
    assert row["matched_duplicate"] is None


def test_reupload_after_confirmation_is_duplicate_and_not_imported_twice(
    client: TestClient, db_session: Session
) -> None:
    family, user = _create_family_and_user(db_session)
    account = _create_account(db_session, family, user)
    first_upload = _upload_statement_preview(client, family, user)
    batch_id = first_upload.json()["summary"]["import_batch_id"]
    first_confirm = client.post(
        f"/api/v1/imports/{batch_id}/confirm",
        params={"account_id": str(account.id)},
    )
    assert first_confirm.status_code == 200
    assert first_confirm.json()["created_transactions"] == 2

    second_upload = _upload_statement_preview(client, family, user)
    second_batch_id = second_upload.json()["summary"]["import_batch_id"]
    duplicate_rows = second_upload.json()["rows"]
    assert all(row["status"] == "duplicate_candidate" for row in duplicate_rows)
    assert all(row["duplicate_transaction_id"] for row in duplicate_rows)
    assert all(row["matched_duplicate"] for row in duplicate_rows)

    second_confirm = client.post(
        f"/api/v1/imports/{second_batch_id}/confirm",
        params={"account_id": str(account.id)},
    )
    assert second_confirm.status_code == 200
    assert second_confirm.json()["created_transactions"] == 0
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


def test_create_import_preview_ignores_client_family_and_uploader_ids(
    client: TestClient,
    db_session: Session,
) -> None:
    caller_family = Family(name="Caller")
    target_family = Family(name="Target")
    user = User(
        family=caller_family,
        email="owner@example.com",
        password_hash="hash",
        display_name="Owner",
    )
    db_session.add_all([caller_family, target_family, user])
    db_session.commit()

    response = client.post(
        "/api/v1/imports/preview",
        params={
            "family_id": str(target_family.id),
            "uploaded_by_user_id": "00000000-0000-0000-0000-000000000000",
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
    batch = db_session.scalar(select(ImportBatch))
    assert batch is not None
    assert batch.family_id == caller_family.id
    assert batch.uploaded_by_user_id == user.id


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


def _create_foreign_preview(db_session: Session, family: Family, user: User) -> ImportBatch:
    row = ParsedBankOperation(
        row_number=3,
        status="auto_ready",
        reason_codes=[],
        occurred_at=datetime(2026, 5, 8, 15, 25),
        amount=Decimal("-118.02"),
        currency="UAH",
        transaction_amount=Decimal("118.02"),
        transaction_currency="UAH",
        balance_after=Decimal("1000.00"),
        payment_instrument_label="4627 **** **** 3421",
        bank_category_raw="Супермаркети та продукти",
        description_raw="Сільпо",
        merchant_name="Сільпо",
        proposed_flow_type="purchase",
        proposed_scope="family",
        confidence=Decimal("0.9000"),
        error_message=None,
        normalized_payload={"direction": "expense"},
    )
    summary = BankStatementSummary(
        period_start=None,
        period_end=None,
        total_rows=1,
        auto_ready_count=1,
        needs_review_count=0,
        imported_count=1,
        excluded_count=0,
        duplicate_count=0,
        error_count=0,
        uncategorized_count=0,
        work_fop_count=0,
        savings_count=0,
        parser_version="test-parser",
        mapping_version="test-mapping",
    )
    return ImportPreviewService(db_session).create_from_parsed_statement(
        family_id=family.id,
        uploaded_by_user_id=user.id,
        parsed_statement=BankStatementParseResult(
            source_filename="foreign.xlsx",
            sheet_name="Виписки",
            summary=summary,
            rows=[row],
        ),
    )
