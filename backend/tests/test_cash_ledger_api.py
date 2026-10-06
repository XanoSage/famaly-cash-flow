from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from auth_helpers import current_test_user_dependency
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.analytics.categories import CategoryAnalyticsService
from app.analytics.merchants import MerchantAnalyticsService
from app.analytics.summary import AnalyticsSummaryService
from app.analytics.timeline import TimelineAnalyticsService
from app.auth.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.family import Family
from app.models.import_batch import ImportBatch
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


def test_cash_wallet_is_idempotent_and_family_scoped(
    client: TestClient,
    db_session: Session,
) -> None:
    family, _, _ = _seed(db_session)
    user = db_session.scalar(select(User).where(User.email == "cash-owner@example.test"))
    assert user is not None
    _authenticate_as(user)
    other_family, _, _ = _seed(db_session, "other@example.test", "Other Family")

    first = client.post("/api/v1/accounts/cash-wallet")
    second = client.post("/api/v1/accounts/cash-wallet")

    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["currency"] == "UAH"
    wallet = db_session.get(Account, UUID(first.json()["id"]))
    assert wallet is not None
    assert wallet.family_id == family.id
    assert wallet.type == "cash"
    assert wallet.owner_user_id is None
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Account)
            .where(
                Account.family_id == family.id,
                Account.type == "cash",
                Account.is_active.is_(True),
            )
        )
        == 1
    )
    assert other_family.id != family.id


def test_manual_withdrawal_and_cash_expense_preserve_analytics_and_pair_delete(
    client: TestClient,
    db_session: Session,
) -> None:
    family, user, card = _seed(db_session)
    _authenticate_as(user)
    category = Category(family=family, name="Food")
    db_session.add(category)
    db_session.commit()
    wallet_response = client.post("/api/v1/accounts/cash-wallet")
    wallet_id = UUID(wallet_response.json()["id"])

    baseline_income = TransactionService(db_session).create_income(
        user=user,
        account_id=card.id,
        amount=Decimal("25000.00"),
        occurred_at=datetime(2026, 10, 6, 9, tzinfo=UTC),
        merchant_name="Salary",
    )
    baseline_expense = TransactionService(db_session).create_expense(
        user=user,
        account_id=card.id,
        amount=Decimal("100.00"),
        occurred_at=datetime(2026, 10, 6, 10, tzinfo=UTC),
        merchant_name="Grocer",
        category_id=category.id,
    )
    before = AnalyticsSummaryService(db_session).build(family_id=family.id)

    withdrawal_response = client.post(
        "/api/v1/cash/transfers",
        json={
            "source_account_id": str(card.id),
            "amount": "5000.00",
            "occurred_at": "2026-10-06T11:00:00+03:00",
            "description": "ATM",
        },
    )
    assert withdrawal_response.status_code == 201, withdrawal_response.text
    transfer_body = withdrawal_response.json()
    source = db_session.get(Transaction, UUID(transfer_body["source_transaction_id"]))
    destination = db_session.get(Transaction, UUID(transfer_body["destination_transaction_id"]))
    assert source is not None and destination is not None
    assert source.amount == Decimal("-5000.00")
    assert destination.amount == Decimal("5000.00")
    assert source.direction == destination.direction == "transfer"
    assert source.transfer_group_id == destination.transfer_group_id
    assert source.transfer_group_id is not None
    assert source.transfer_role == "source"
    assert destination.transfer_role == "destination"
    assert source.currency == destination.currency == "UAH"
    assert transfer_body["cash_balance"] == "5000.00"

    summary_after_transfer = AnalyticsSummaryService(db_session).build(family_id=family.id)
    assert summary_after_transfer.income == before.income == Decimal("25000.00")
    assert summary_after_transfer.expenses == before.expenses == Decimal("100.00")
    assert summary_after_transfer.net_cash_flow == before.net_cash_flow
    assert summary_after_transfer.transfers == Decimal("5000.00")
    assert summary_after_transfer.transfer_count == 1
    assert CategoryAnalyticsService(db_session).build(family_id=family.id).total_amount == Decimal(
        "100.00"
    )
    assert MerchantAnalyticsService(db_session).build(family_id=family.id).total_amount == Decimal(
        "100.00"
    )
    timeline = TimelineAnalyticsService(db_session).build(family_id=family.id)
    assert timeline.rows[-1].expenses == Decimal("100.00")
    assert timeline.rows[-1].transfer_count == 1

    expense_response = client.post(
        "/api/v1/cash/expenses",
        json={
            "amount": "450.00",
            "occurred_at": "2026-10-06T12:00:00+03:00",
            "merchant_name": "Market",
            "category_id": str(category.id),
        },
    )
    assert expense_response.status_code == 201, expense_response.text
    cash_expense = db_session.get(Transaction, UUID(expense_response.json()["id"]))
    assert cash_expense is not None
    assert cash_expense.account_id == wallet_id
    assert cash_expense.amount == Decimal("-450.00")
    assert cash_expense.direction == "expense"
    assert cash_expense.flow_type == "cash_expense"
    assert cash_expense.is_cash is True
    assert client.get("/api/v1/cash/summary").json()["balance"] == "4550.00"
    summary_after_expense = AnalyticsSummaryService(db_session).build(family_id=family.id)
    assert summary_after_expense.expenses == Decimal("550.00")
    assert summary_after_expense.expense_count == 2
    assert CategoryAnalyticsService(db_session).build(family_id=family.id).total_amount == Decimal(
        "550.00"
    )
    assert MerchantAnalyticsService(db_session).build(family_id=family.id).total_amount == Decimal(
        "550.00"
    )
    assert TimelineAnalyticsService(db_session).build(family_id=family.id).rows[
        -1
    ].expenses == Decimal("550.00")

    assert client.delete(f"/api/v1/transactions/{cash_expense.id}").status_code == 204
    assert client.get("/api/v1/cash/summary").json()["balance"] == "5000.00"
    transfer_audit_count = db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.entity_id.in_([source.id, destination.id]))
    )
    assert client.delete(f"/api/v1/transactions/{source.id}").status_code == 204
    assert client.get("/api/v1/cash/summary").json()["balance"] == "0.00"
    assert db_session.get(Transaction, source.id).deleted_at is not None
    assert db_session.get(Transaction, destination.id).deleted_at is not None
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.entity_id.in_([source.id, destination.id]), AuditLog.action == "delete")
        )
        == 2
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.entity_id.in_([source.id, destination.id]))
        )
        == transfer_audit_count + 2
    )
    after_pair_delete = AnalyticsSummaryService(db_session).build(family_id=family.id)
    assert after_pair_delete.transfers == Decimal("0.00")
    assert after_pair_delete.expenses == Decimal("100.00")
    assert db_session.get(Transaction, baseline_income.id) is not None
    assert db_session.get(Transaction, baseline_expense.id) is not None


def test_transfer_pair_rejects_patch_and_invalid_accounts(
    client: TestClient, db_session: Session
) -> None:
    _, user, card = _seed(db_session)
    _authenticate_as(user)
    wallet = client.post("/api/v1/accounts/cash-wallet").json()
    created = client.post(
        "/api/v1/cash/transfers",
        json={"source_account_id": str(card.id), "amount": "0.01"},
    )
    assert created.status_code == 201, created.text
    source_id = created.json()["source_transaction_id"]
    assert (
        client.patch(f"/api/v1/transactions/{source_id}", json={"amount": "1.00"}).status_code
        == 422
    )

    same_account = client.post(
        "/api/v1/cash/transfers",
        json={"source_account_id": wallet["id"], "amount": "1.00"},
    )
    assert same_account.status_code == 422

    _, _, foreign_card = _seed(db_session, "foreign@example.test", "Foreign")
    foreign = client.post(
        "/api/v1/cash/transfers",
        json={"source_account_id": str(foreign_card.id), "amount": "1.00"},
    )
    assert foreign.status_code == 422

    family = db_session.get(Family, card.family_id)
    owner = db_session.get(User, card.owner_user_id)
    assert family is not None and owner is not None
    usd_card = Account(
        family=family,
        owner_user=owner,
        type="card",
        name="USD card",
        currency="USD",
    )
    db_session.add(usd_card)
    usd_card.currency = "USD"
    db_session.commit()
    mismatch = client.post(
        "/api/v1/cash/transfers",
        json={"source_account_id": str(usd_card.id), "amount": "1.00"},
    )
    assert mismatch.status_code == 422


def test_imported_cash_withdrawal_links_only_the_cash_destination(
    client: TestClient,
    db_session: Session,
) -> None:
    family, user, card = _seed(db_session)
    _authenticate_as(user)
    wallet_id = UUID(client.post("/api/v1/accounts/cash-wallet").json()["id"])
    batch = ImportBatch(
        family_id=family.id,
        uploaded_by_user_id=user.id,
        source_filename="synthetic.xlsx",
        status="confirmed",
        total_rows=1,
        parser_version="test",
        mapping_version="test",
    )
    source = Transaction(
        family_id=family.id,
        account_id=card.id,
        owner_user_id=user.id,
        import_batch=batch,
        bank_transaction_id="cash-atm-row-1",
        occurred_at=datetime(2026, 10, 6, 10, tzinfo=UTC),
        amount=Decimal("-5000.00"),
        currency="UAH",
        direction="expense",
        flow_type="cash_withdrawal",
        scope="family",
        description_raw="ATM cash withdrawal",
        needs_review=True,
    )
    db_session.add(source)
    db_session.commit()
    source_id = source.id

    response = client.post(f"/api/v1/cash/imported-withdrawals/{source_id}/link")

    assert response.status_code == 201, response.text
    body = response.json()
    db_session.refresh(source)
    destination = db_session.get(Transaction, UUID(body["destination_transaction_id"]))
    assert destination is not None
    assert source.id == source_id
    assert source.amount == Decimal("-5000.00")
    assert source.direction == "transfer"
    assert source.transfer_role == "source"
    assert destination.amount == Decimal("5000.00")
    assert destination.account_id == wallet_id
    assert destination.import_batch_id is None
    assert destination.transfer_group_id == source.transfer_group_id
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.bank_transaction_id == "cash-atm-row-1")
        )
        == 1
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.entity_id.in_([source.id, destination.id]))
        )
        == 2
    )
    summary = AnalyticsSummaryService(db_session).build(family_id=family.id)
    assert summary.expenses == Decimal("0.00")
    assert summary.income == Decimal("0.00")
    assert summary.transfer_count == 1
    assert client.get("/api/v1/cash/summary").json()["balance"] == "5000.00"
    repeated = client.post(f"/api/v1/cash/imported-withdrawals/{source_id}/link")
    assert repeated.status_code == 422
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.transfer_group_id == source.transfer_group_id)
        )
        == 2
    )


def test_cash_transfer_audit_failure_rolls_back_both_legs(db_session: Session) -> None:
    _, user, card = _seed(db_session)
    TransactionService(db_session).ensure_cash_wallet(user=user)

    def fail_audit(session, *_):
        if any(isinstance(item, AuditLog) for item in session.new):
            raise RuntimeError("synthetic audit persistence failure")

    event.listen(db_session, "before_flush", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="synthetic audit persistence failure"):
            TransactionService(db_session).create_cash_withdrawal(
                user=user,
                source_account_id=card.id,
                amount=Decimal("5000.00"),
            )
    finally:
        event.remove(db_session, "before_flush", fail_audit)
    db_session.expire_all()
    assert db_session.scalar(select(Transaction)) is None
    assert db_session.scalar(select(AuditLog)) is None


def test_cash_wallet_missing_and_currency_precision(
    client: TestClient, db_session: Session
) -> None:
    family, user, card = _seed(db_session)
    _authenticate_as(user)
    without_wallet = client.post(
        "/api/v1/cash/expenses",
        json={"amount": "0.01", "occurred_at": "2026-10-06T10:00:00Z"},
    )
    assert without_wallet.status_code == 422
    assert "cash wallet" in without_wallet.json()["detail"].lower()

    client.post("/api/v1/accounts/cash-wallet")
    for amount in ("0.01", "450.00", "5000.00"):
        withdrawal = client.post(
            "/api/v1/cash/transfers",
            json={"source_account_id": str(card.id), "amount": amount},
        )
        assert withdrawal.status_code == 201, withdrawal.text
        stored_source = db_session.get(
            Transaction, UUID(withdrawal.json()["source_transaction_id"])
        )
        stored_cash = db_session.get(
            Transaction, UUID(withdrawal.json()["destination_transaction_id"])
        )
        assert stored_source is not None and stored_cash is not None
        assert stored_source.amount == -Decimal(amount)
        assert stored_cash.amount == Decimal(amount)
        assert isinstance(stored_cash.amount, Decimal)
    assert family.id == card.family_id


def _seed(
    db: Session,
    email: str = "cash-owner@example.test",
    name: str = "Cash Family",
) -> tuple[Family, User, Account]:
    family = Family(name=name)
    user = User(family=family, email=email, password_hash="hash", display_name="Owner")
    account = Account(
        family=family,
        owner_user=user,
        type="card",
        name="Main card",
        currency="UAH",
    )
    db.add_all([family, user, account])
    db.commit()
    return family, user, account


def _authenticate_as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user
