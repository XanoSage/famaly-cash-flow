from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app import models  # noqa: F401
from app.api.routes import auth as auth_routes
from app.auth.service import hash_password, hash_refresh_token, new_refresh_token
from app.db.base import Base
from app.db.session import get_db
from app.importers.bank_xlsx import (
    BankStatementParseResult,
    BankStatementSummary,
    ParsedBankOperation,
)
from app.main import app
from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.family import Family
from app.models.import_batch import ImportBatch, ImportPreviewRow
from app.models.telegram_identity import TelegramIdentity, TelegramLinkToken
from app.models.transaction import Transaction
from app.models.user import AuthSession, User, UserPreference
from app.services.confirm_import import ConfirmImportError, ConfirmImportService
from app.services.import_preview import ImportPreviewService
from app.services.import_review import ImportReviewService
from app.services.telegram_linking import (
    consume_telegram_link_token,
    create_telegram_link,
    hash_telegram_link_token,
)
from app.services.transactions import TransactionService

pytestmark = pytest.mark.postgres


def test_auth_refresh_rotation_replay_revocation_and_concurrency(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    _, user, _ = _seed_user(postgres_session_factory, "auth@example.test")
    previous_override = app.dependency_overrides.get(get_db)

    def override_get_db():
        with postgres_session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": "synthetic-integration-password"},
            )
            assert login_response.status_code == 200
            original_token = login_response.cookies.get("refresh_token")
            if not original_token:
                pytest.fail("Auth login did not set a refresh cookie.", pytrace=False)

            original_session = _session_for_hash(
                postgres_session_factory, hash_refresh_token(original_token)
            )
            assert original_session is not None
            old_hash = original_session.refresh_token_hash

            rotation = client.post(
                "/api/v1/auth/refresh", cookies={"refresh_token": original_token}
            )
            assert rotation.status_code == 200
            rotated_token = rotation.cookies.get("refresh_token")
            if not rotated_token:
                pytest.fail("Refresh response omitted the rotated cookie.", pytrace=False)
            _require_safe(
                rotated_token != original_token,
                "Refresh reused the original credential.",
            )
            assert (
                _session_for_hash(postgres_session_factory, hash_refresh_token(rotated_token))
                is not None
            )
            assert _session_for_hash(postgres_session_factory, old_hash) is None

            replay = client.post("/api/v1/auth/refresh", cookies={"refresh_token": original_token})
            assert replay.status_code == 401
            logout = client.post("/api/v1/auth/logout", cookies={"refresh_token": rotated_token})
            assert logout.status_code == 204
            revoked_refresh = client.post(
                "/api/v1/auth/refresh", cookies={"refresh_token": rotated_token}
            )
            assert revoked_refresh.status_code == 401
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

    concurrent_token = new_refresh_token()
    with postgres_session_factory.begin() as db:
        db.add(
            AuthSession(
                user_id=user.id,
                refresh_token_hash=hash_refresh_token(concurrent_token),
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )

    barrier = Barrier(2, timeout=10)

    def refresh_once() -> tuple[bool, int]:
        with postgres_session_factory() as db:
            db.execute(text("SET LOCAL lock_timeout = '6s'"))
            db.execute(text("SET LOCAL statement_timeout = '12s'"))
            backend_pid = db.scalar(text("SELECT pg_backend_pid()"))
            barrier.wait()
            try:
                auth_routes.refresh(Response(), concurrent_token, db)
                return True, backend_pid
            except HTTPException as exc:
                assert exc.status_code == 401
                return False, backend_pid

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [
            future.result(timeout=20) for future in [pool.submit(refresh_once) for _ in range(2)]
        ]

    assert len({pid for _, pid in outcomes}) == 2
    assert sum(succeeded for succeeded, _ in outcomes) == 1
    with postgres_session_factory() as db:
        stored_hashes = db.scalars(
            select(AuthSession.refresh_token_hash).where(AuthSession.user_id == user.id)
        ).all()
    _require_safe(
        hash_refresh_token(concurrent_token) not in stored_hashes,
        "The original concurrent refresh credential remained stored.",
    )
    assert len(stored_hashes) == 2  # The original login session remains revoked after logout.


def test_telegram_link_is_consumed_once_and_under_concurrency(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    _, first_user, _ = _seed_user(postgres_session_factory, "telegram-one@example.test")
    with postgres_session_factory() as db:
        link = create_telegram_link(db, user_id=first_user.id, bot_username=None)
        assert consume_telegram_link_token(
            db,
            raw_token=link.token,
            telegram_user_id=81001,
            private_chat_id=91001,
            profile={"username": "synthetic"},
        )
        assert not consume_telegram_link_token(
            db,
            raw_token=link.token,
            telegram_user_id=81001,
            private_chat_id=91001,
            profile={},
        )
    with postgres_session_factory() as db:
        identity = db.scalar(
            select(TelegramIdentity).where(TelegramIdentity.user_id == first_user.id)
        )
        token = db.scalar(
            select(TelegramLinkToken).where(
                TelegramLinkToken.token_hash == hash_telegram_link_token(link.token)
            )
        )
        assert identity is not None and identity.telegram_user_id == 81001
        assert token is not None and token.used_at is not None

    _, second_user, _ = _seed_user(postgres_session_factory, "telegram-two@example.test")
    with postgres_session_factory() as db:
        concurrent_link = create_telegram_link(db, user_id=second_user.id, bot_username=None)
    barrier = Barrier(2, timeout=10)

    def consume_once(telegram_user_id: int) -> tuple[bool, int]:
        with postgres_session_factory() as db:
            db.execute(text("SET LOCAL lock_timeout = '6s'"))
            db.execute(text("SET LOCAL statement_timeout = '12s'"))
            backend_pid = db.scalar(text("SELECT pg_backend_pid()"))
            barrier.wait()
            succeeded = consume_telegram_link_token(
                db,
                raw_token=concurrent_link.token,
                telegram_user_id=telegram_user_id,
                private_chat_id=91002,
                profile={},
            )
            return succeeded, backend_pid

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [
            future.result(timeout=20)
            for future in [pool.submit(consume_once, user_id) for user_id in (82001, 82002)]
        ]

    assert len({pid for _, pid in outcomes}) == 2
    assert sum(succeeded for succeeded, _ in outcomes) == 1
    with postgres_session_factory() as db:
        linked = db.scalars(
            select(TelegramIdentity).where(TelegramIdentity.user_id == second_user.id)
        ).all()
        assert len(linked) == 1
        assert linked[0].telegram_user_id in {82001, 82002}


def test_telegram_identity_insert_failure_rolls_back_token_consumption(
    postgres_session_factory: sessionmaker[Session],
    postgres_engine,
) -> None:
    _, user, _ = _seed_user(postgres_session_factory, "telegram-atomic@example.test")
    with postgres_session_factory() as db:
        link = create_telegram_link(db, user_id=user.id, bot_username=None)

    with postgres_engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE OR REPLACE FUNCTION test_reject_telegram_identity_insert() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'synthetic identity insert rejection' USING ERRCODE = '23505'; "
            "END; $$"
        )
        connection.exec_driver_sql(
            "CREATE TRIGGER test_reject_telegram_identity_insert "
            "BEFORE INSERT ON telegram_identities FOR EACH ROW "
            "EXECUTE FUNCTION test_reject_telegram_identity_insert()"
        )
    try:
        with postgres_session_factory() as db:
            consumed = consume_telegram_link_token(
                db,
                raw_token=link.token,
                telegram_user_id=83001,
                private_chat_id=93001,
                profile={},
            )
        assert consumed is False
    finally:
        with postgres_engine.begin() as connection:
            connection.exec_driver_sql(
                "DROP TRIGGER IF EXISTS test_reject_telegram_identity_insert ON telegram_identities"
            )
            connection.exec_driver_sql(
                "DROP FUNCTION IF EXISTS test_reject_telegram_identity_insert()"
            )

    with postgres_session_factory() as db:
        token = db.scalar(
            select(TelegramLinkToken).where(
                TelegramLinkToken.token_hash == hash_telegram_link_token(link.token)
            )
        )
        identity = db.scalar(select(TelegramIdentity))
        assert token is not None and token.used_at is None
        assert identity is None


def test_postgres_enforces_application_unique_and_foreign_key_constraints(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    family, user, account = _seed_user(postgres_session_factory, "constraint@example.test")
    _, other_user, _ = _seed_user(postgres_session_factory, "other@example.test")
    now = datetime.now(UTC)
    with postgres_session_factory.begin() as db:
        db.add(
            TelegramIdentity(
                user_id=user.id,
                telegram_user_id=84001,
                private_chat_id=94001,
                linked_at=now,
                last_seen_at=now,
            )
        )
        db.add(
            AuthSession(
                user_id=user.id,
                refresh_token_hash="d" * 64,
                expires_at=now + timedelta(days=1),
            )
        )

    _assert_integrity_error(
        postgres_session_factory,
        User(
            family_id=other_user.family_id,
            email=user.email,
            password_hash="synthetic",
            display_name="Duplicate email",
        ),
    )
    _assert_integrity_error(
        postgres_session_factory,
        TelegramIdentity(
            user_id=other_user.id,
            telegram_user_id=84001,
            private_chat_id=94001,
            linked_at=now,
            last_seen_at=now,
        ),
    )
    _assert_integrity_error(
        postgres_session_factory,
        TelegramIdentity(
            user_id=user.id,
            telegram_user_id=84002,
            private_chat_id=94002,
            linked_at=now,
            last_seen_at=now,
        ),
    )
    token_hash = "a" * 64
    with postgres_session_factory.begin() as db:
        db.add(
            TelegramLinkToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=now + timedelta(minutes=5),
            )
        )
    _assert_integrity_error(
        postgres_session_factory,
        TelegramLinkToken(
            user_id=other_user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(minutes=5),
        ),
    )
    _assert_integrity_error(
        postgres_session_factory,
        AuthSession(
            user_id=user.id,
            refresh_token_hash="d" * 64,
            expires_at=now + timedelta(days=1),
        ),
    )

    batch = ImportBatch(
        family_id=family.id,
        uploaded_by_user_id=user.id,
        source_filename="synthetic.xlsx",
        parser_version="test",
        mapping_version="test",
    )
    with postgres_session_factory.begin() as db:
        db.add(batch)
    preview_values = {
        "import_batch_id": batch.id,
        "row_number": 3,
        "status": "auto_ready",
    }
    with postgres_session_factory.begin() as db:
        db.add(ImportPreviewRow(**preview_values))
    _assert_integrity_error(postgres_session_factory, ImportPreviewRow(**preview_values))

    with postgres_session_factory.begin() as db:
        db.add(
            UserPreference(
                user_id=user.id,
                default_account_id=account.id,
                language="en",
            )
        )
    _assert_integrity_error(
        postgres_session_factory,
        UserPreference(user_id=user.id, language="uk"),
    )
    _assert_integrity_error(
        postgres_session_factory,
        AuthSession(
            user_id=uuid4(),
            refresh_token_hash="b" * 64,
            expires_at=now + timedelta(days=1),
        ),
    )
    _assert_integrity_error(
        postgres_session_factory,
        TelegramLinkToken(
            user_id=uuid4(),
            token_hash="c" * 64,
            expires_at=now + timedelta(minutes=5),
        ),
    )
    _assert_integrity_error(
        postgres_session_factory,
        TelegramIdentity(
            user_id=uuid4(),
            telegram_user_id=84003,
            private_chat_id=94003,
            linked_at=now,
            last_seen_at=now,
        ),
    )
    _assert_integrity_error(
        postgres_session_factory,
        UserPreference(user_id=uuid4(), language="en"),
    )
    _assert_integrity_error(
        postgres_session_factory,
        UserPreference(user_id=other_user.id, default_account_id=uuid4(), language="en"),
    )
    _assert_integrity_error(
        postgres_session_factory,
        ImportPreviewRow(
            import_batch_id=uuid4(),
            row_number=4,
            status="auto_ready",
        ),
    )

    with postgres_session_factory.begin() as db:
        account_to_delete = db.get(Account, account.id)
        assert account_to_delete is not None
        db.delete(account_to_delete)
    with postgres_session_factory() as db:
        preference = db.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
        assert preference is not None and preference.default_account_id is None


def test_postgres_import_review_confirmation_and_decimal_persistence(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    family, user, account = _seed_user(postgres_session_factory, "import@example.test")
    occurred_at = datetime(2026, 10, 5, 12, 34, tzinfo=UTC)
    amount = Decimal("-1234.56")
    category = Category(family_id=family.id, name="Integration groceries")
    existing = Transaction(
        family_id=family.id,
        account_id=account.id,
        occurred_at=occurred_at,
        amount=amount,
        currency="UAH",
        direction="expense",
        flow_type="purchase",
        scope="family",
        description_raw="Market purchase",
        description_normalized="market purchase",
    )
    with postgres_session_factory.begin() as db:
        db.add_all([category, existing])

    parsed = BankStatementParseResult(
        source_filename="synthetic-statement.xlsx",
        sheet_name="Operations",
        summary=BankStatementSummary(
            period_start=occurred_at,
            period_end=occurred_at,
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
            parser_version="integration-test",
            mapping_version="integration-test",
        ),
        rows=[
            ParsedBankOperation(
                row_number=3,
                status="auto_ready",
                reason_codes=[],
                occurred_at=occurred_at,
                amount=amount,
                currency="UAH",
                transaction_amount=Decimal("-1234.56"),
                transaction_currency="UAH",
                balance_after=Decimal("8765.44"),
                payment_instrument_label="synthetic card 1234",
                bank_category_raw="Groceries",
                description_raw="Market purchase",
                merchant_name="Market",
                proposed_flow_type="purchase",
                proposed_scope="family",
                confidence=Decimal("0.9000"),
                error_message=None,
                normalized_payload={"direction": "expense"},
            )
        ],
    )
    with postgres_session_factory() as db:
        batch = ImportPreviewService(db).create_from_parsed_statement(
            family_id=family.id,
            uploaded_by_user_id=user.id,
            parsed_statement=parsed,
        )
        preview = db.scalar(
            select(ImportPreviewRow).where(ImportPreviewRow.import_batch_id == batch.id)
        )
        assert preview is not None
        assert preview.status == "duplicate_candidate"
        assert preview.duplicate_transaction_id == existing.id
        result = ImportReviewService(db).patch_row(
            family_id=family.id,
            import_batch_id=batch.id,
            row_id=preview.id,
            changes={"include_duplicate": True, "proposed_category_id": category.id},
        )
        assert result.changed_count == 1
        preview_id = preview.id
        batch_id = batch.id

    with postgres_session_factory() as db:
        reviewed = db.get(ImportPreviewRow, preview_id)
        assert reviewed is not None
        assert reviewed.duplicate_included is True
        assert reviewed.proposed_category_id == category.id
        confirmed = ConfirmImportService(db).confirm(
            family_id=family.id,
            import_batch_id=batch_id,
            account_id=account.id,
            owner_user_id=user.id,
        )
        assert len(confirmed) == 1
        imported_id = confirmed[0].id
        with pytest.raises(ConfirmImportError):
            ConfirmImportService(db).confirm(
                family_id=family.id,
                import_batch_id=batch_id,
                account_id=account.id,
                owner_user_id=user.id,
            )

    with postgres_session_factory() as db:
        imported = db.get(Transaction, imported_id)
        saved_batch = db.get(ImportBatch, batch_id)
        assert imported is not None and saved_batch is not None
        _require_safe(
            imported.amount == Decimal("-1234.56")
            and imported.transaction_amount == Decimal("-1234.56")
            and imported.balance_after == Decimal("8765.44")
            and isinstance(imported.amount, Decimal),
            "Imported NUMERIC fields did not retain the expected Decimal values.",
        )
        _require_safe(
            imported.occurred_at == occurred_at,
            "The import did not retain the expected timezone-aware timestamp.",
        )
        assert imported.is_duplicate_candidate is True
        assert imported.category_id == category.id
        assert saved_batch.status == "confirmed"
        assert (
            db.scalar(
                select(func.count())
                .select_from(Transaction)
                .where(Transaction.import_batch_id == batch_id)
            )
            == 1
        )


def test_postgres_manual_transaction_audit_and_soft_delete_persistence(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    family, user, account = _seed_user(postgres_session_factory, "manual-audit@example.test")
    with postgres_session_factory() as db:
        service = TransactionService(db)
        transaction = service.create_expense(
            user=user,
            account_id=account.id,
            amount=Decimal("1234.56"),
            occurred_at=datetime(2026, 10, 5, 18, 45, tzinfo=UTC),
            merchant_name="Synthetic PostgreSQL market",
            comment="Synthetic audit integration test",
        )
        transaction_id = transaction.id
        service.update(
            user=user,
            transaction_id=transaction_id,
            changes={"amount": Decimal("1234.57"), "comment": "Updated synthetic comment"},
        )
        service.soft_delete(user=user, transaction_id=transaction_id)

    with postgres_session_factory() as db:
        retained = db.get(Transaction, transaction_id)
        audits = db.scalars(
            select(AuditLog)
            .where(AuditLog.entity_type == "transaction", AuditLog.entity_id == transaction_id)
            .order_by(AuditLog.created_at, AuditLog.action)
        ).all()
        assert retained is not None
        _require_safe(
            retained.amount == Decimal("-1234.57") and isinstance(retained.amount, Decimal),
            "The PostgreSQL transaction amount did not retain its Decimal value.",
        )
        assert retained.deleted_at is not None
        assert retained.deleted_by_user_id == user.id
        assert retained.owner_user_id == user.id
        assert len(audits) == 3
        assert [audit.action for audit in audits] == ["create", "update", "delete"]
        assert all(audit.family_id == family.id and audit.user_id == user.id for audit in audits)
        assert audits[0].after_payload["amount"] == "-1234.56"
        assert audits[1].before_payload["amount"] == "-1234.56"
        assert audits[1].after_payload["amount"] == "-1234.57"
        assert audits[2].after_payload["deleted_by_user_id"] == str(user.id)


def _seed_user(session_factory: sessionmaker[Session], email: str) -> tuple[Family, User, Account]:
    family = Family(name="Synthetic integration family")
    user = User(
        family=family,
        email=email,
        password_hash=hash_password("synthetic-integration-password"),
        display_name="Integration tester",
    )
    account = Account(
        family=family,
        owner_user=user,
        type="card",
        name="Synthetic test account",
        currency="UAH",
    )
    with session_factory.begin() as db:
        db.add_all([family, user, account])
    return family, user, account


def _session_for_hash(
    session_factory: sessionmaker[Session], token_hash: str
) -> AuthSession | None:
    with session_factory() as db:
        return db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash))


def _assert_integrity_error(session_factory: sessionmaker[Session], row: Base) -> None:
    with pytest.raises(IntegrityError):
        with session_factory.begin() as db:
            db.add(row)


def _require_safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)
