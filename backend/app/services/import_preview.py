from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.bank_xlsx import BankStatementParseResult, parse_bank_xlsx
from app.models.import_batch import ImportBatch, ImportPreviewRow
from app.models.user import User

DRAFT_IMPORT_TTL_DAYS = 7


class ImportPreviewError(ValueError):
    pass


class ImportPreviewService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_from_xlsx(
        self,
        *,
        family_id: UUID,
        uploaded_by_user_id: UUID,
        path: str | Path,
        source_filename: str | None = None,
    ) -> ImportBatch:
        self._ensure_user_belongs_to_family(family_id, uploaded_by_user_id)
        parsed_statement = parse_bank_xlsx(path)
        if source_filename:
            parsed_statement = replace(parsed_statement, source_filename=source_filename)
        return self.create_from_parsed_statement(
            family_id=family_id,
            uploaded_by_user_id=uploaded_by_user_id,
            parsed_statement=parsed_statement,
        )

    def create_from_parsed_statement(
        self,
        *,
        family_id: UUID,
        uploaded_by_user_id: UUID,
        parsed_statement: BankStatementParseResult,
    ) -> ImportBatch:
        self._ensure_user_belongs_to_family(family_id, uploaded_by_user_id)

        summary = parsed_statement.summary
        import_batch = ImportBatch(
            family_id=family_id,
            uploaded_by_user_id=uploaded_by_user_id,
            source_filename=parsed_statement.source_filename,
            period_start=summary.period_start,
            period_end=summary.period_end,
            status="draft",
            total_rows=summary.total_rows,
            imported_count=summary.imported_count,
            excluded_count=summary.excluded_count,
            duplicate_count=summary.duplicate_count,
            error_count=summary.error_count,
            uncategorized_count=summary.uncategorized_count,
            work_fop_count=summary.work_fop_count,
            savings_count=summary.savings_count,
            parser_version=summary.parser_version,
            mapping_version=summary.mapping_version,
            expires_at=datetime.now(UTC) + timedelta(days=DRAFT_IMPORT_TTL_DAYS),
        )
        self.db.add(import_batch)
        self.db.flush()

        self.db.add_all(
            [
                ImportPreviewRow(
                    import_batch_id=import_batch.id,
                    row_number=row.row_number,
                    status=row.status,
                    reason_codes=row.reason_codes,
                    occurred_at=row.occurred_at,
                    amount=row.amount,
                    currency=row.currency,
                    transaction_amount=row.transaction_amount,
                    transaction_currency=row.transaction_currency,
                    balance_after=row.balance_after,
                    payment_instrument_label=row.payment_instrument_label,
                    bank_category_raw=row.bank_category_raw,
                    description_raw=row.description_raw,
                    merchant_name=row.merchant_name,
                    proposed_flow_type=row.proposed_flow_type,
                    proposed_scope=row.proposed_scope,
                    confidence=row.confidence,
                    error_message=row.error_message,
                    normalized_payload=row.normalized_payload,
                )
                for row in parsed_statement.rows
            ]
        )
        self.db.commit()
        self.db.refresh(import_batch)
        return import_batch

    def _ensure_user_belongs_to_family(self, family_id: UUID, uploaded_by_user_id: UUID) -> None:
        user = self.db.scalar(
            select(User).where(
                User.id == uploaded_by_user_id,
                User.family_id == family_id,
            )
        )
        if user is None:
            raise ImportPreviewError("Uploader does not belong to the target family.")
