from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from jwt import encode
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.auth.service import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
)
from app.core.config import Settings, settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.account import Account
from app.models.family import Family
from app.models.import_batch import ImportBatch
from app.models.transaction import Transaction
from app.models.user import AuthSession, User, UserPreference

PASSWORD = "local-test-password"


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


def test_login_normalizes_email_returns_access_token_and_sets_hashed_refresh_cookie(
    client: TestClient,
    db_session: Session,
) -> None:
    family, user = _create_user(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "  OWNER@EXAMPLE.COM ", "password": PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.jwt_access_token_expire_minutes * 60
    assert body["access_token"]
    assert user.password_hash.startswith("$argon2id$")
    claims = __import__("jwt").decode(
        body["access_token"], settings.jwt_secret_key, algorithms=["HS256"]
    )
    assert claims["sub"] == str(user.id)
    assert claims["typ"] == "access"
    assert "family_id" not in claims

    raw_refresh_token = response.cookies.get("refresh_token")
    assert raw_refresh_token
    assert "refresh_token" not in body
    assert "httponly" in response.headers["set-cookie"].lower()
    session = db_session.scalar(select(AuthSession))
    assert session is not None
    assert session.user_id == user.id
    assert session.refresh_token_hash == hash_refresh_token(raw_refresh_token)
    assert session.refresh_token_hash != raw_refresh_token
    assert user.family_id == family.id


@pytest.mark.parametrize(
    "email,password", [("owner@example.com", "wrong"), ("missing@example.com", PASSWORD)]
)
def test_login_rejects_wrong_password_and_unknown_email(
    client: TestClient,
    db_session: Session,
    email: str,
    password: str,
) -> None:
    _create_user(db_session)

    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_inactive_user_cannot_login(client: TestClient, db_session: Session) -> None:
    _create_user(db_session, is_active=False)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": PASSWORD},
    )

    assert response.status_code == 401


def test_user_email_is_unique_across_families(db_session: Session) -> None:
    _create_user(db_session, email="owner@example.com", family_name="Family A")
    family_b = Family(name="Family B")
    user_b = User(
        family=family_b,
        email="owner@example.com",
        password_hash=hash_password(PASSWORD),
        display_name="Second owner",
    )
    db_session.add_all([family_b, user_b])

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_production_auth_configuration_requires_secure_cookie() -> None:
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret_key="a" * 32,
            auth_cookie_secure=False,
        )


def test_me_returns_authenticated_user_and_family(client: TestClient, db_session: Session) -> None:
    family, user = _create_user(db_session)
    db_session.add(UserPreference(user=user, language="uk"))
    db_session.commit()
    token = _issue_access_token(db_session, user)

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "display_name": "Owner",
        "email": "owner@example.com",
        "language": "uk",
        "family_id": str(family.id),
        "family_name": "Test Family",
    }
    assert "password_hash" not in response.json()


def test_me_requires_access_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("token_kind", ["expired", "invalid"])
def test_me_rejects_expired_or_invalid_access_token(
    client: TestClient,
    db_session: Session,
    token_kind: str,
) -> None:
    _, user = _create_user(db_session)
    refresh = new_refresh_token()
    auth_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.add(auth_session)
    db_session.commit()
    if token_kind == "expired":
        token = encode(
            {
                "sub": str(user.id),
                "sid": str(auth_session.id),
                "typ": "access",
                "iat": datetime.now(UTC) - timedelta(minutes=30),
                "exp": datetime.now(UTC) - timedelta(minutes=15),
            },
            settings.jwt_secret_key,
            algorithm="HS256",
        )
    else:
        token = "not.a.valid-token"

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_refresh_rotates_refresh_token_and_rejects_reuse(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_user(db_session)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": PASSWORD},
    )
    old_refresh_token = login_response.cookies["refresh_token"]

    refresh_response = client.post("/api/v1/auth/refresh")

    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"] != login_response.json()["access_token"]
    new_raw_token = refresh_response.cookies["refresh_token"]
    assert new_raw_token != old_refresh_token
    session = db_session.scalar(select(AuthSession))
    assert session is not None
    assert session.refresh_token_hash == hash_refresh_token(new_raw_token)
    assert session.refresh_token_hash != hash_refresh_token(old_refresh_token)

    client.cookies.set("refresh_token", old_refresh_token, path="/api/v1/auth")
    reuse_response = client.post("/api/v1/auth/refresh")

    assert reuse_response.status_code == 401


def test_logout_revokes_refresh_session_and_access_token(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_user(db_session)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": PASSWORD},
    )
    access_token = login_response.json()["access_token"]

    logout_response = client.post("/api/v1/auth/logout")

    assert logout_response.status_code == 204
    session = db_session.scalar(select(AuthSession))
    assert session is not None
    assert session.revoked_at is not None
    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    refresh_response = client.post("/api/v1/auth/refresh")
    assert me_response.status_code == 401
    assert refresh_response.status_code == 401
    client.cookies.set(
        "refresh_token", login_response.cookies["refresh_token"], path="/api/v1/auth"
    )
    revoked_reuse_response = client.post("/api/v1/auth/refresh")
    assert revoked_reuse_response.status_code == 401


def test_user_cannot_access_or_mutate_another_familys_transactions(
    client: TestClient,
    db_session: Session,
) -> None:
    family_a, user_a = _create_user(db_session, email="a@example.com", family_name="Family A")
    family_b, user_b = _create_user(db_session, email="b@example.com", family_name="Family B")
    account_a = _create_account(db_session, family_a, user_a)
    account_b = _create_account(db_session, family_b, user_b)
    transaction_a = _create_transaction(db_session, family_a, account_a, "Family A transaction")
    transaction_b = _create_transaction(db_session, family_b, account_b, "Family B transaction")
    access_token = _issue_access_token(db_session, user_a)
    headers = {"Authorization": f"Bearer {access_token}"}

    list_response = client.get(
        "/api/v1/transactions",
        params={"family_id": str(family_b.id)},
        headers=headers,
    )
    mutate_response = client.patch(
        f"/api/v1/transactions/{transaction_b.id}",
        params={"family_id": str(family_a.id)},
        headers=headers,
        json={"comment": "attempted change"},
    )
    account_filter_response = client.get(
        "/api/v1/transactions",
        params={"account_id": str(account_b.id)},
        headers=headers,
    )

    assert list_response.status_code == 200
    assert [row["id"] for row in list_response.json()["rows"]] == [str(transaction_a.id)]
    assert mutate_response.status_code == 404
    assert account_filter_response.status_code == 404
    db_session.refresh(transaction_b)
    assert transaction_b.comment is None


def test_user_cannot_read_or_confirm_another_familys_import(
    client: TestClient,
    db_session: Session,
) -> None:
    family_a, user_a = _create_user(db_session, email="a@example.com", family_name="Family A")
    family_b, user_b = _create_user(db_session, email="b@example.com", family_name="Family B")
    _create_account(db_session, family_a, user_a)
    account_b = _create_account(db_session, family_b, user_b)
    mismatched_owner_account = Account(
        family=family_a,
        owner_user=user_b,
        type="card",
        name="Invalid owner family",
        currency="UAH",
    )
    db_session.add(mismatched_owner_account)
    db_session.commit()
    batch_a = _create_import_batch(db_session, family_a, user_a)
    batch_b = _create_import_batch(db_session, family_b, user_b)
    access_token = _issue_access_token(db_session, user_a)
    headers = {"Authorization": f"Bearer {access_token}"}

    foreign_read = client.get(f"/api/v1/imports/{batch_b.id}/preview", headers=headers)
    foreign_confirm = client.post(
        f"/api/v1/imports/{batch_b.id}/confirm",
        params={"account_id": str(account_b.id)},
        headers=headers,
    )
    foreign_account_confirm = client.post(
        f"/api/v1/imports/{batch_a.id}/confirm",
        params={"account_id": str(account_b.id)},
        headers=headers,
    )
    mismatched_owner_confirm = client.post(
        f"/api/v1/imports/{batch_a.id}/confirm",
        params={"account_id": str(mismatched_owner_account.id)},
        headers=headers,
    )

    assert foreign_read.status_code == 404
    assert foreign_confirm.status_code == 404
    assert foreign_account_confirm.status_code == 404
    assert mismatched_owner_confirm.status_code == 404
    assert batch_a.family_id == family_a.id


def test_import_creation_ignores_client_family_and_uploader_ids(
    client: TestClient,
    db_session: Session,
) -> None:
    family_a, user_a = _create_user(db_session, email="a@example.com", family_name="Family A")
    family_b, user_b = _create_user(db_session, email="b@example.com", family_name="Family B")
    access_token = _issue_access_token(db_session, user_a)

    response = client.post(
        "/api/v1/imports/preview",
        params={
            "family_id": str(family_b.id),
            "uploaded_by_user_id": str(user_b.id),
        },
        headers={"Authorization": f"Bearer {access_token}"},
        files={
            "file": (
                "statement.xlsx",
                _make_statement_xlsx(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 201
    import_batch_id = UUID(response.json()["summary"]["import_batch_id"])
    batch = db_session.scalar(select(ImportBatch).where(ImportBatch.id == import_batch_id))
    assert batch is not None
    assert batch.family_id == family_a.id
    assert batch.uploaded_by_user_id == user_a.id


def _create_user(
    db_session: Session,
    *,
    email: str = "owner@example.com",
    family_name: str = "Test Family",
    is_active: bool = True,
) -> tuple[Family, User]:
    family = Family(name=family_name)
    user = User(
        family=family,
        email=email.strip().lower(),
        password_hash=hash_password(PASSWORD),
        display_name="Owner",
        is_active=is_active,
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


def _create_transaction(
    db_session: Session,
    family: Family,
    account: Account,
    description: str,
) -> Transaction:
    transaction = Transaction(
        family=family,
        account=account,
        occurred_at=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        amount=Decimal("-10.00"),
        currency="UAH",
        direction="expense",
        flow_type="purchase",
        scope="family",
        description_raw=description,
    )
    db_session.add(transaction)
    db_session.commit()
    return transaction


def _create_import_batch(db_session: Session, family: Family, user: User) -> ImportBatch:
    batch = ImportBatch(
        family=family,
        uploaded_by_user=user,
        source_filename="statement.xlsx",
        status="draft",
        parser_version="test",
        mapping_version="test",
    )
    db_session.add(batch)
    db_session.commit()
    return batch


def _issue_access_token(db_session: Session, user: User) -> str:
    refresh_token = new_refresh_token()
    auth_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.add(auth_session)
    db_session.commit()
    return create_access_token(user.id, auth_session.id)


def _make_statement_xlsx() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Виписки"
    worksheet.append(["Історія операцій за період 01.10.2026 - 01.10.2026"])
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
            "01.10.2026 12:00:00",
            "Супермаркети та продукти",
            "4627 **** **** 3421",
            "Сільпо",
            -10,
            "UAH",
            10,
            "UAH",
            100,
            "UAH",
        ]
    )
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
