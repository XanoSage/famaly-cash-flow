from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.importers.bank_xlsx import BankStatementParseResult, BankStatementSummary, ParsedBankOperation
from app.models.family import Family
from app.models.import_batch import ImportBatch, ImportPreviewRow
from app.models.user import User
from app.services.import_preview import ImportPreviewError, ImportPreviewService


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


def test_import_preview_service_persists_batch_and_rows(db_session: Session) -> None:
    family = Family(name="Test Family")
    user = User(
        family=family,
        email="owner@example.com",
        password_hash="hash",
        display_name="Owner",
    )
    db_session.add_all([family, user])
    db_session.commit()

    parsed_statement = _parsed_statement()
    import_batch = ImportPreviewService(db_session).create_from_parsed_statement(
        family_id=family.id,
        uploaded_by_user_id=user.id,
        parsed_statement=parsed_statement,
    )

    saved_batch = db_session.get(ImportBatch, import_batch.id)
    assert saved_batch is not None
    assert saved_batch.status == "draft"
    assert saved_batch.source_filename == "statement.xlsx"
    assert saved_batch.total_rows == 2
    assert saved_batch.savings_count == 1
    assert saved_batch.expires_at is not None

    rows = db_session.scalars(
        select(ImportPreviewRow)
        .where(ImportPreviewRow.import_batch_id == import_batch.id)
        .order_by(ImportPreviewRow.row_number)
    ).all()
    assert len(rows) == 2
    assert rows[0].merchant_name == "Сільпо"
    assert rows[0].status == "auto_ready"
    assert rows[1].reason_codes == ["person_transfer"]
    assert rows[1].status == "needs_review"


def test_import_preview_service_rejects_user_from_other_family(db_session: Session) -> None:
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

    with pytest.raises(ImportPreviewError):
        ImportPreviewService(db_session).create_from_parsed_statement(
            family_id=target_family.id,
            uploaded_by_user_id=user.id,
            parsed_statement=_parsed_statement(),
        )


def _parsed_statement() -> BankStatementParseResult:
    period_start = datetime(2026, 2, 8)
    period_end = datetime(2026, 5, 8)
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
    return BankStatementParseResult(
        source_filename="statement.xlsx",
        sheet_name="Виписки",
        summary=BankStatementSummary(
            period_start=period_start,
            period_end=period_end,
            total_rows=2,
            auto_ready_count=1,
            needs_review_count=1,
            imported_count=2,
            excluded_count=0,
            duplicate_count=0,
            error_count=0,
            uncategorized_count=0,
            work_fop_count=0,
            savings_count=1,
            parser_version="bank-xlsx-v1",
            mapping_version="preview-rules-v1",
        ),
        rows=rows,
    )
