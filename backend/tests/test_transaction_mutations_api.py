from collections.abc import Generator
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from auth_helpers import current_test_user_dependency
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.auth.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.category import Category, Subcategory
from app.models.family import Family
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.models.user import User
from app.services.transactions import TransactionService


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
    app.dependency_overrides[get_current_user] = current_test_user_dependency(db_session)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_expense_normalizes_positive_decimal_and_audits(
    client: TestClient,
    db_session: Session,
) -> None:
    family, user, account = _seed(db_session)
    category = Category(family=family, name="Food")
    subcategory = Subcategory(category=category, name="Groceries")
    db_session.add_all([category, subcategory])
    db_session.commit()

    response = client.post(
        "/api/v1/transactions",
        json={
            "direction": "expense",
            "amount": "450.25",
            "account_id": str(account.id),
            "occurred_at": "2026-08-01T12:00:00+03:00",
            "merchant_name": "  ATB   Market ",
            "category_id": str(category.id),
            "subcategory_id": str(subcategory.id),
            "scope": "family",
            "comment": "Manual entry",
        },
    )

    assert response.status_code == 201
    body = response.json()
    transaction = db_session.get(Transaction, UUID(body["id"]))
    assert transaction is not None
    assert transaction.family_id == family.id
    assert transaction.owner_user_id == user.id
    assert transaction.amount == Decimal("-450.25")
    assert transaction.direction == "expense"
    assert transaction.flow_type == "purchase"
    assert transaction.income_type is None
    assert transaction.occurred_at == datetime(2026, 8, 1, 9, 0)
    assert body["occurred_at"].endswith("Z")
    assert body["account_name"] == account.name
    assert body["display_description"] == "ATB Market"
    assert body["category_name"] == "Food"
    assert body["subcategory_name"] == "Groceries"
    audit = _audit(db_session, transaction.id, "create")
    assert audit.user_id == user.id
    assert audit.family_id == family.id
    assert audit.entity_type == "transaction"
    assert audit.before_payload is None
    assert audit.after_payload["amount"] == "-450.25"
    assert audit.after_payload["occurred_at"] == "2026-08-01T09:00:00+00:00"


def test_create_income_is_positive_and_omitted_timestamp_is_aware(
    client: TestClient,
    db_session: Session,
) -> None:
    _, _, account = _seed(db_session)

    response = client.post(
        "/api/v1/transactions",
        json={
            "direction": "income",
            "amount": "25000.00",
            "account_id": str(account.id),
            "income_type": "refund",
            "merchant_name": "Returned purchase",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    transaction = db_session.get(Transaction, UUID(payload["id"]))
    assert transaction is not None
    assert transaction.amount == Decimal("25000.00")
    assert transaction.direction == "income"
    assert transaction.flow_type == "refund"
    assert transaction.income_type == "refund"
    assert payload["occurred_at"].endswith("Z")
    assert _audit(db_session, transaction.id, "create") is not None


@pytest.mark.parametrize("amount", ["0", "-1", "1.234", "NaN"])
def test_manual_amount_rejects_nonpositive_or_overprecision_values(
    client: TestClient,
    db_session: Session,
    amount: str,
) -> None:
    _, _, account = _seed(db_session)

    response = client.post(
        "/api/v1/transactions",
        json={"direction": "expense", "amount": amount, "account_id": str(account.id)},
    )

    assert response.status_code == 422
    assert db_session.scalar(select(Transaction)) is None
    assert db_session.scalar(select(AuditLog)) is None


def test_manual_timestamp_requires_offset_and_create_does_not_accept_family_id(
    client: TestClient,
    db_session: Session,
) -> None:
    _, _, account = _seed(db_session)
    base = {"direction": "expense", "amount": "1.00", "account_id": str(account.id)}

    naive = client.post(
        "/api/v1/transactions",
        json={**base, "occurred_at": "2026-08-01T12:00:00"},
    )
    family_parameter = client.post(
        "/api/v1/transactions",
        json={**base, "family_id": str(uuid4())},
    )

    assert naive.status_code == 422
    assert family_parameter.status_code == 422


def test_accounts_categories_and_subcategories_are_validated_in_family(
    client: TestClient,
    db_session: Session,
) -> None:
    family, user, account = _seed(db_session)
    app.dependency_overrides[get_current_user] = lambda: user
    foreign_family, _, foreign_account = _seed(
        db_session,
        email="foreign@example.test",
        name="Foreign Family",
    )
    same_category = Category(family=family, name="Food")
    foreign_category = Category(family=foreign_family, name="Private")
    vegetables = Subcategory(category=same_category, name="Vegetables")
    fruit = Subcategory(category=same_category, name="Fruit")
    system_category = Category(family_id=None, name="System", is_system=True)
    db_session.add_all([same_category, foreign_category, vegetables, fruit, system_category])
    db_session.commit()

    def create(**overrides):
        return client.post(
            "/api/v1/transactions",
            json={
                "direction": "expense",
                "amount": "10.00",
                "account_id": str(account.id),
                **overrides,
            },
        )

    valid_custom = create(category_id=str(same_category.id), subcategory_id=str(vegetables.id))
    valid_system = create(category_id=str(system_category.id))
    foreign_account_result = create(account_id=str(foreign_account.id))
    foreign_category_result = create(category_id=str(foreign_category.id))
    invalid_subcategory = create(category_id=str(same_category.id), subcategory_id=str(uuid4()))
    subcategory_without_category = create(subcategory_id=str(vegetables.id))

    assert valid_custom.status_code == 201
    assert valid_custom.json()["subcategory_name"] == "Vegetables"
    assert valid_system.status_code == 201
    assert foreign_account_result.status_code == 422
    assert foreign_category_result.status_code == 422
    assert invalid_subcategory.status_code == 422
    assert subcategory_without_category.status_code == 422

    account.is_active = False
    db_session.commit()
    inactive = create()
    assert inactive.status_code == 422


def test_merchant_reuse_and_uncategorized_manual_review(
    client: TestClient,
    db_session: Session,
) -> None:
    family, _, account = _seed(db_session)
    merchant = Merchant(
        family=family,
        name="АТБ",
        normalized_name="атб",
        merchant_type="store",
    )
    db_session.add(merchant)
    db_session.commit()

    response = client.post(
        "/api/v1/transactions",
        json={
            "direction": "expense",
            "amount": "12.00",
            "account_id": str(account.id),
            "merchant_name": "  АТБ   ",
        },
    )

    assert response.status_code == 201
    transaction = db_session.get(Transaction, UUID(response.json()["id"]))
    assert transaction is not None
    assert transaction.merchant_id == merchant.id
    assert transaction.needs_review is True
    assert transaction.category_id is None


def test_get_transaction_hides_foreign_and_deleted_rows(
    client: TestClient,
    db_session: Session,
) -> None:
    _, user, account = _seed(db_session)
    transaction = Transaction(
        family_id=user.family_id,
        account_id=account.id,
        occurred_at=datetime(2026, 8, 1, 12, 0),
        amount=Decimal("-10.00"),
        currency="UAH",
        direction="expense",
        flow_type="purchase",
        scope="family",
    )
    db_session.add(transaction)
    db_session.commit()
    own = client.get(f"/api/v1/transactions/{transaction.id}")
    assert own.status_code == 200

    _, foreign_user, _ = _seed(db_session, email="foreign-get@example.test")
    app.dependency_overrides[get_current_user] = lambda: foreign_user
    foreign = client.get(f"/api/v1/transactions/{transaction.id}")
    assert foreign.status_code == 404
    assert foreign.json()["detail"] == "Transaction not found."

    app.dependency_overrides[get_current_user] = lambda: user
    transaction.deleted_at = datetime(2026, 8, 2, 12, 0)
    db_session.commit()
    deleted = client.get(f"/api/v1/transactions/{transaction.id}")
    assert deleted.status_code == 404


def test_update_fields_sign_normalization_audit_and_noop_behavior(
    client: TestClient,
    db_session: Session,
) -> None:
    family, user, account = _seed(db_session)
    category = Category(family_id=family.id, name="Corrected")
    db_session.add(category)
    db_session.flush()
    subcategory = Subcategory(category_id=category.id, name="Household")
    transaction = Transaction(
        family_id=family.id,
        account_id=account.id,
        owner_user_id=user.id,
        occurred_at=datetime(2026, 8, 1, 12, 0),
        amount=Decimal("-20.00"),
        currency="UAH",
        direction="expense",
        flow_type="purchase",
        scope="family",
        description_raw="Bank original",
        description_normalized="bank original",
        needs_review=True,
    )
    db_session.add_all([category, subcategory])
    db_session.flush()
    db_session.add(transaction)
    db_session.commit()

    amount_edit = client.patch(
        f"/api/v1/transactions/{transaction.id}",
        json={"amount": "875.25"},
    )
    income_edit = client.patch(
        f"/api/v1/transactions/{transaction.id}",
        json={
            "direction": "income",
            "income_type": "debt",
            "category_id": str(category.id),
            "subcategory_id": str(subcategory.id),
            "merchant_name": "Corrected Name",
            "scope": "personal_main_user",
            "comment": "Corrected comment",
            "needs_review": False,
        },
    )

    assert amount_edit.status_code == 200
    assert amount_edit.json()["amount"] == "-875.25"
    assert income_edit.status_code == 200
    db_session.refresh(transaction)
    assert transaction.amount == Decimal("875.25")
    assert transaction.direction == "income"
    assert transaction.flow_type == "income"
    assert transaction.income_type == "debt"
    assert transaction.category_id == category.id
    assert transaction.subcategory_id == subcategory.id
    assert transaction.description_raw == "Bank original"
    assert transaction.description_override == "Corrected Name"
    assert transaction.comment == "Corrected comment"
    assert transaction.scope == "personal_main_user"
    update_audits = db_session.scalars(
        select(AuditLog).where(AuditLog.entity_id == transaction.id, AuditLog.action == "update")
    ).all()
    assert len(update_audits) == 2
    assert update_audits[0].user_id == user.id
    assert update_audits[0].before_payload["amount"] == "-20.00"
    assert update_audits[0].after_payload["amount"] == "-875.25"
    assert update_audits[1].before_payload["merchant_name"] == "bank original"
    assert update_audits[1].after_payload["merchant_name"] == "Corrected Name"

    count_before_noop = db_session.scalar(select(func.count()).select_from(AuditLog))
    noop = client.patch(
        f"/api/v1/transactions/{transaction.id}",
        json={"comment": "Corrected comment"},
    )
    count_after_noop = db_session.scalar(select(func.count()).select_from(AuditLog))
    assert noop.status_code == 200
    assert count_after_noop == count_before_noop


def test_update_rejects_foreign_category_naive_timestamp_and_provenance_fields(
    client: TestClient,
    db_session: Session,
) -> None:
    family, user, account = _seed(db_session)
    transaction = Transaction(
        family_id=family.id,
        account_id=account.id,
        occurred_at=datetime(2026, 8, 1, 12, 0),
        amount=Decimal("-20.00"),
        currency="UAH",
        direction="expense",
        flow_type="purchase",
        scope="family",
    )
    foreign_family, _, _ = _seed(db_session, email="foreign-category@example.test")
    foreign_category = Category(family=foreign_family, name="Private")
    db_session.add_all([transaction, foreign_category])
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user

    foreign = client.patch(
        f"/api/v1/transactions/{transaction.id}",
        json={"category_id": str(foreign_category.id)},
    )
    naive = client.patch(
        f"/api/v1/transactions/{transaction.id}",
        json={"occurred_at": "2026-08-01T12:30:00"},
    )
    immutable = client.patch(
        f"/api/v1/transactions/{transaction.id}",
        json={"family_id": str(family.id), "deleted_at": None},
    )

    assert foreign.status_code == 422
    assert naive.status_code == 422
    assert immutable.status_code == 422


def test_soft_delete_is_idempotent_and_removed_from_list_summary_and_category_analytics(
    client: TestClient,
    db_session: Session,
) -> None:
    family, user, account = _seed(db_session)
    category = Category(family=family, name="Food")
    db_session.add(category)
    db_session.commit()
    created = client.post(
        "/api/v1/transactions",
        json={
            "direction": "expense",
            "amount": "25.00",
            "account_id": str(account.id),
            "category_id": str(category.id),
        },
    )
    assert created.status_code == 201
    transaction_id = UUID(created.json()["id"])
    summary_before = client.get("/api/v1/analytics/summary").json()
    category_before = client.get("/api/v1/analytics/by-category").json()
    audit_before = db_session.scalar(select(func.count()).select_from(AuditLog))

    first_delete = client.delete(f"/api/v1/transactions/{transaction_id}")
    second_delete = client.delete(f"/api/v1/transactions/{transaction_id}")

    assert first_delete.status_code == 204
    assert second_delete.status_code == 204
    stored = db_session.get(Transaction, transaction_id)
    assert stored is not None
    assert stored.deleted_at is not None
    assert stored.deleted_by_user_id == user.id
    assert db_session.scalar(select(func.count()).select_from(AuditLog)) == audit_before + 1
    delete_audit = _audit(db_session, transaction_id, "delete")
    assert delete_audit.before_payload == {"deleted_at": None, "deleted_by_user_id": None}
    assert delete_audit.after_payload["deleted_by_user_id"] == str(user.id)
    assert client.get(f"/api/v1/transactions/{transaction_id}").status_code == 404
    assert client.get("/api/v1/transactions").json()["total"] == 0
    include_deleted = client.get("/api/v1/transactions", params={"include_deleted": "true"})
    assert include_deleted.json()["total"] == 1

    summary_after = client.get("/api/v1/analytics/summary").json()
    category_after = client.get("/api/v1/analytics/by-category").json()
    assert summary_before["expenses"] == "25.00"
    assert summary_before["transaction_count"] == 1
    assert summary_after["expenses"] == "0.00"
    assert summary_after["transaction_count"] == 0
    assert category_before["total_amount"] == "25.00"
    assert category_after["total_amount"] == "0.00"


def test_audit_failure_rolls_back_transaction_and_merchant_creation(db_session: Session) -> None:
    _, user, account = _seed(db_session)

    def fail_audit(session, *_):
        if any(isinstance(item, AuditLog) for item in session.new):
            raise RuntimeError("synthetic audit persistence failure")

    event.listen(db_session, "before_flush", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="synthetic audit persistence failure"):
            TransactionService(db_session).create_expense(
                user=user,
                account_id=account.id,
                amount=Decimal("10.00"),
                merchant_name="Atomic Merchant",
            )
    finally:
        event.remove(db_session, "before_flush", fail_audit)
    db_session.expire_all()
    assert db_session.scalar(select(Transaction)) is None
    assert db_session.scalar(select(Merchant)) is None
    assert db_session.scalar(select(AuditLog)) is None


def _seed(
    db_session: Session,
    *,
    email: str = "owner@example.test",
    name: str = "Test Family",
) -> tuple[Family, User, Account]:
    family = Family(name=name)
    user = User(
        family=family,
        email=email,
        password_hash="hash",
        display_name="Test User",
    )
    account = Account(
        family=family,
        owner_user=user,
        type="card",
        name="Main card",
        currency="UAH",
    )
    db_session.add_all([family, user, account])
    db_session.commit()
    return family, user, account


def _audit(db_session: Session, entity_id, action: str) -> AuditLog:
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.entity_type == "transaction",
            AuditLog.entity_id == entity_id,
            AuditLog.action == action,
        )
    )
    assert audit is not None
    return audit
