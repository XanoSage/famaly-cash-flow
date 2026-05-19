from __future__ import annotations

from collections import Counter
from pathlib import Path
import shutil
import tempfile
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.importers.bank_xlsx import BankXlsxParseError
from app.models.import_batch import ImportBatch, ImportPreviewRow
from app.schemas.imports import ImportPreviewResponse, ImportPreviewRowResponse, ImportPreviewSummary
from app.services.import_preview import ImportPreviewError, ImportPreviewService

router = APIRouter(prefix="/imports")


@router.post(
    "/preview",
    response_model=ImportPreviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_import_preview(
    family_id: UUID = Query(...),
    uploaded_by_user_id: UUID = Query(...),
    preview_limit: int = Query(50, ge=1, le=200),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportPreviewResponse:
    _validate_xlsx_upload(file)
    temp_path = _save_upload_to_temp_file(file)
    try:
        import_batch = ImportPreviewService(db).create_from_xlsx(
            family_id=family_id,
            uploaded_by_user_id=uploaded_by_user_id,
            path=temp_path,
            source_filename=file.filename,
        )
    except (BankXlsxParseError, ImportPreviewError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    rows = db.scalars(
        select(ImportPreviewRow)
        .where(ImportPreviewRow.import_batch_id == import_batch.id)
        .order_by(ImportPreviewRow.row_number)
        .limit(preview_limit)
    ).all()
    all_statuses = db.scalars(
        select(ImportPreviewRow.status).where(ImportPreviewRow.import_batch_id == import_batch.id)
    ).all()
    status_counts = Counter(all_statuses)

    return _to_response(import_batch, rows, status_counts)


def _validate_xlsx_upload(file: UploadFile) -> None:
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx files are supported.",
        )


def _save_upload_to_temp_file(file: UploadFile) -> Path:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
        shutil.copyfileobj(file.file, temp_file)
        return Path(temp_file.name)


def _to_response(
    import_batch: ImportBatch,
    rows: list[ImportPreviewRow],
    status_counts: Counter[str],
) -> ImportPreviewResponse:
    row_responses = [
        ImportPreviewRowResponse(
            id=row.id,
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
        for row in rows
    ]
    return ImportPreviewResponse(
        summary=ImportPreviewSummary(
            import_batch_id=import_batch.id,
            source_filename=import_batch.source_filename,
            status=import_batch.status,
            period_start=import_batch.period_start,
            period_end=import_batch.period_end,
            total_rows=import_batch.total_rows,
            returned_rows=len(row_responses),
            auto_ready_count=status_counts["auto_ready"],
            needs_review_count=status_counts["needs_review"],
            imported_count=import_batch.imported_count,
            excluded_count=import_batch.excluded_count,
            duplicate_count=import_batch.duplicate_count,
            error_count=import_batch.error_count,
            uncategorized_count=import_batch.uncategorized_count,
            work_fop_count=import_batch.work_fop_count,
            savings_count=import_batch.savings_count,
            parser_version=import_batch.parser_version,
            mapping_version=import_batch.mapping_version,
            expires_at=import_batch.expires_at,
        ),
        rows=row_responses,
    )
