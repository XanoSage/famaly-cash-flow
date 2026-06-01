from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.importers.bank_xlsx import BankStatementParseResult, BankStatementSummary, ParsedBankOperation
from app.models.account import Account, PaymentInstrument
from app.models.family import Family
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.models.user import User
from app.services.confirm_import import ConfirmImportError, ConfirmImportService
from app.services.import_preview import ImportPreviewService


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session


def test_confirm_import_creates_transactions_merchants_and_payment_instruments(
    db_session: Session,
) -> None:
    family, user, account = _create_family_user_and_account(db_session)
    import_batch = ImportPreviewService(db_session).create_from_parsed_statement(
        family_id=family.id,
        uploaded_by_user_id=user.id,
        parsed_statement=_parsed_statement(),
    )

    transactions = ConfirmImportService(db_session).confirm(
        family_id=family.id,
        import_batch_id=import_batch.id,
        account_id=account.id,
    )

    assert len(transactions) == 2
    assert import_batch.status == "confirmed"
    assert db_session.query(Transaction).count() == 2
    assert db_session.query(Merchant).count() == 2
    assert db_session.query(PaymentInstrument).count() == 1

    first_transaction = transactions[0]
    assert first_transaction.amount == Decimal("-118.02")
    assert first_transaction.direction == "expense"
    assert first_transaction.flow_type == "purchase"
    assert first_transaction.needs_review is False
    assert first_transaction.owner_user_id == user.id

    second_transaction = transactions[1]
    assert second_transaction.needs_review is True
    assert second_transaction.flow_type == "person_transfer"


def test_confirm_import_blocks_error_rows(db_session: Session) -> None:
    family, user, account = _create_family_user_and_account(db_session)
    import_batch = ImportPreviewService(db_session).create_from_parsed_statement(
        family_id=family.id,
        uploaded_by_user_id=user.id,
        parsed_statement=_parsed_statement_with_error(),
    )

    with pytest.raises(ConfirmImportError):
        ConfirmImportService(db_session).confirm(
            family_id=family.id,
            import_batch_id=import_batch.id,
            account_id=account.id,
        )

    assert import_batch.status == "draft"
    assert db_session.query(Transaction).count() == 0


def _create_family_user_and_account(db_session: Session) -> tuple[Family, User, Account]:
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
    db_session.add_all([family, user, account])
    db_session.commit()
    return family, user, account


def _parsed_statement() -> BankStatementParseResult:
    rows = [
        ParsedBankOperation(
            row_number=3,
            status="auto_ready",
            reason_codes=[],
            occurred_at=datetime(2026, 5, 8, 15, 25),
            amount=Decimal("-118.02"),
            currency="UAH",
            transaction_amount=Decimal("118.02"),
            transaction_currency="UAH",
            balance_after=Decimal("6248.97"),
            payment_instrument_label="4627 **** **** 3421",
            bank_category_raw="Супермаркети та продукти",
            description_raw="Сільпо",
            merchant_name="Сільпо",
            proposed_flow_type="purchase",
            proposed_scope="family",
            confidence=Decimal("0.9000"),
            error_message=None,
            normalized_payload={"direction": "expense"},
        ),
        ParsedBankOperation(
            row_number=4,
            status="needs_review",
            reason_codes=["person_transfer"],
            occurred_at=datetime(2026, 5, 8, 10, 0),
            amount=Decimal("-700.00"),
            currency="UAH",
            transaction_amount=Decimal("700.00"),
            transaction_currency="UAH",
            balance_after=Decimal("1000.00"),
            payment_instrument_label="4627 **** **** 3421",
            bank_category_raw="Перекази",
            description_raw="Переказ на картку",
            merchant_name="Переказ на картку",
            proposed_flow_type="person_transfer",
            proposed_scope="family",
            confidence=Decimal("0.6000"),
            error_message=None,
            normalized_payload={"direction": "expense"},
        ),
    ]
    return _statement(rows=rows, error_count=0)


def _parsed_statement_with_error() -> BankStatementParseResult:
    rows = [
        ParsedBankOperation(
            row_number=3,
            status="error",
            reason_codes=["parse_error"],
            occurred_at=None,
            amount=None,
            currency=None,
            transaction_amount=None,
            transaction_currency=None,
            balance_after=None,
            payment_instrument_label=None,
            bank_category_raw=None,
            description_raw=None,
            merchant_name=None,
            proposed_flow_type=None,
            proposed_scope=None,
            confidence=None,
            error_message="date is empty",
            normalized_payload={},
        )
    ]
    return _statement(rows=rows, error_count=1)


def _statement(rows: list[ParsedBankOperation], error_count: int) -> BankStatementParseResult:
    return BankStatementParseResult(
        source_filename="statement.xlsx",
        sheet_name="Виписки",
        summary=BankStatementSummary(
            period_start=datetime(2026, 2, 8),
            period_end=datetime(2026, 5, 8),
            total_rows=len(rows),
            auto_ready_count=sum(row.status == "auto_ready" for row in rows),
            needs_review_count=sum(row.status == "needs_review" for row in rows),
            imported_count=sum(row.status != "error" for row in rows),
            excluded_count=0,
            duplicate_count=0,
            error_count=error_count,
            uncategorized_count=0,
            work_fop_count=0,
            savings_count=0,
            parser_version="bank-xlsx-v1",
            mapping_version="preview-rules-v1",
        ),
        rows=rows,
    )
