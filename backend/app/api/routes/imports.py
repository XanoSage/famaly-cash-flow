from __future__ import annotations

import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.authorization import require_family_account
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.importers.bank_xlsx import BankXlsxParseError
from app.models.import_batch import ImportBatch, ImportPreviewRow
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.imports import (
    ConfirmImportResponse,
    ImportBulkActionRequest,
    ImportPreviewResponse,
    ImportPreviewRowPatchRequest,
    ImportPreviewRowResponse,
    ImportPreviewSummary,
    ImportReviewActionResponse,
    ImportReviewSummary,
    MatchedDuplicateSummary,
)
from app.services.confirm_import import ConfirmImportError, ConfirmImportService
from app.services.import_preview import ImportPreviewError, ImportPreviewService
from app.services.import_review import (
    ImportDraftNotFoundError,
    ImportReviewError,
    ImportReviewService,
    ImportReviewValidationError,
)

router = APIRouter(prefix="/imports")


@router.post(
    "/preview",
    response_model=ImportPreviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_import_preview(
    current_user: User = Depends(get_current_user),
    preview_limit: int = Query(50, ge=1, le=200),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportPreviewResponse:
    _validate_xlsx_upload(file)
    temp_path = _save_upload_to_temp_file(file)
    try:
        import_batch = ImportPreviewService(db).create_from_xlsx(
            family_id=current_user.family_id,
            uploaded_by_user_id=current_user.id,
            path=temp_path,
            source_filename=file.filename,
        )
    except (BankXlsxParseError, ImportPreviewError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    rows = _get_preview_rows(
        db,
        import_batch.id,
        limit=preview_limit,
    )
    status_counts = _get_status_counts(db, import_batch.id)
    return _to_response(
        db,
        current_user.family_id,
        import_batch,
        rows,
        status_counts,
        offset=0,
        limit=preview_limit,
    )


@router.get(
    "/{import_batch_id}/preview",
    response_model=ImportPreviewResponse,
)
def get_import_preview(
    import_batch_id: UUID,
    current_user: User = Depends(get_current_user),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    row_status: Literal["auto_ready", "needs_review", "duplicate_candidate", "excluded", "error"]
    | None = Query(None),
    reason_code: str | None = Query(None, min_length=1, max_length=64),
    merchant: str | None = Query(None, min_length=1, max_length=255),
    bank_category: str | None = Query(None, min_length=1, max_length=160),
    proposed_category_id: UUID | None = Query(None),
    uncategorized_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> ImportPreviewResponse:
    import_batch = _get_family_batch(db, current_user.family_id, import_batch_id)
    rows_query = select(ImportPreviewRow).where(ImportPreviewRow.import_batch_id == import_batch.id)
    if row_status is not None:
        rows_query = rows_query.where(ImportPreviewRow.status == row_status)
    if merchant is not None:
        rows_query = rows_query.where(ImportPreviewRow.merchant_name.ilike(f"%{merchant}%"))
    if bank_category is not None:
        rows_query = rows_query.where(
            ImportPreviewRow.bank_category_raw.ilike(f"%{bank_category}%")
        )
    if proposed_category_id is not None:
        rows_query = rows_query.where(ImportPreviewRow.proposed_category_id == proposed_category_id)
    if uncategorized_only:
        rows_query = rows_query.where(ImportPreviewRow.proposed_category_id.is_(None))

    matching_rows = (
        db.scalars(
            rows_query.options(
                joinedload(ImportPreviewRow.proposed_category),
                joinedload(ImportPreviewRow.proposed_subcategory),
            ).order_by(ImportPreviewRow.row_number)
        )
        .unique()
        .all()
    )
    if reason_code is not None:
        matching_rows = [row for row in matching_rows if reason_code in (row.reason_codes or [])]
    total_matching_rows = len(matching_rows)
    rows = matching_rows[offset : offset + limit]
    status_counts = _get_status_counts(db, import_batch.id)
    return _to_response(
        db,
        current_user.family_id,
        import_batch,
        rows,
        status_counts,
        offset=offset,
        limit=limit,
        total_matching_rows=total_matching_rows,
    )


@router.patch(
    "/{import_batch_id}/preview/{row_id}",
    response_model=ImportReviewActionResponse,
)
def patch_import_preview_row(
    import_batch_id: UUID,
    row_id: UUID,
    payload: ImportPreviewRowPatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportReviewActionResponse:
    changes = {
        field: getattr(payload, field)
        for field in payload.model_fields_set
        if field
        not in {
            "save_rule",
            "apply_to_merchant",
        }
    }
    try:
        result = ImportReviewService(db).patch_row(
            family_id=current_user.family_id,
            import_batch_id=import_batch_id,
            row_id=row_id,
            changes=changes,
            save_rule=payload.save_rule,
            apply_to_merchant=payload.apply_to_merchant,
        )
    except ImportReviewError as exc:
        _raise_review_http_error(exc)

    return _action_response(db, current_user.family_id, result)


@router.post(
    "/{import_batch_id}/bulk-actions",
    response_model=ImportReviewActionResponse,
)
def bulk_review_action(
    import_batch_id: UUID,
    payload: ImportBulkActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportReviewActionResponse:
    values = {
        field: getattr(payload, field)
        for field in payload.model_fields_set
        if field
        not in {
            "action",
            "row_ids",
            "save_rule",
            "apply_to_merchant",
        }
    }
    try:
        result = ImportReviewService(db).bulk_action(
            family_id=current_user.family_id,
            import_batch_id=import_batch_id,
            row_ids=payload.row_ids,
            action=payload.action,
            values=values,
            save_rule=payload.save_rule,
            apply_to_merchant=payload.apply_to_merchant,
        )
    except ImportReviewError as exc:
        _raise_review_http_error(exc)

    return _action_response(db, current_user.family_id, result)


@router.post(
    "/{import_batch_id}/confirm",
    response_model=ConfirmImportResponse,
)
def confirm_import_preview(
    import_batch_id: UUID,
    account_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConfirmImportResponse:
    import_batch = _get_family_batch(db, current_user.family_id, import_batch_id)
    require_family_account(db, current_user.family_id, account_id)
    try:
        transactions = ConfirmImportService(db).confirm(
            family_id=current_user.family_id,
            import_batch_id=import_batch_id,
            account_id=account_id,
            owner_user_id=current_user.id,
        )
    except ConfirmImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.refresh(import_batch)
    return ConfirmImportResponse(
        import_batch_id=import_batch_id,
        status=import_batch.status,
        created_transactions=len(transactions),
        excluded_count=import_batch.excluded_count,
        duplicate_count=import_batch.duplicate_count,
        error_count=import_batch.error_count,
        uncategorized_count=import_batch.uncategorized_count,
        work_fop_count=import_batch.work_fop_count,
        savings_count=import_batch.savings_count,
    )


def _get_family_batch(db: Session, family_id: UUID, import_batch_id: UUID) -> ImportBatch:
    batch = db.scalar(
        select(ImportBatch).where(
            ImportBatch.id == import_batch_id,
            ImportBatch.family_id == family_id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="Import preview not found.")
    return batch


def _get_preview_rows(
    db: Session,
    import_batch_id: UUID,
    *,
    limit: int,
) -> list[ImportPreviewRow]:
    return (
        db.scalars(
            select(ImportPreviewRow)
            .options(
                joinedload(ImportPreviewRow.proposed_category),
                joinedload(ImportPreviewRow.proposed_subcategory),
            )
            .where(ImportPreviewRow.import_batch_id == import_batch_id)
            .order_by(ImportPreviewRow.row_number)
            .limit(limit)
        )
        .unique()
        .all()
    )


def _get_status_counts(db: Session, import_batch_id: UUID) -> Counter[str]:
    return Counter(
        db.scalars(
            select(ImportPreviewRow.status).where(
                ImportPreviewRow.import_batch_id == import_batch_id
            )
        ).all()
    )


def _to_response(
    db: Session,
    family_id: UUID,
    import_batch: ImportBatch,
    rows: list[ImportPreviewRow],
    status_counts: Counter[str],
    *,
    offset: int,
    limit: int,
    total_matching_rows: int | None = None,
) -> ImportPreviewResponse:
    duplicate_ids = {row.duplicate_transaction_id for row in rows if row.duplicate_transaction_id}
    duplicate_transactions: dict[UUID, Transaction] = {}
    if duplicate_ids:
        duplicate_transactions = {
            transaction.id: transaction
            for transaction in db.scalars(
                select(Transaction)
                .options(
                    joinedload(Transaction.merchant),
                    joinedload(Transaction.category),
                )
                .where(
                    Transaction.id.in_(duplicate_ids),
                    Transaction.family_id == family_id,
                )
            )
            .unique()
            .all()
        }

    row_responses: list[ImportPreviewRowResponse] = []
    for row in rows:
        duplicate_transaction = duplicate_transactions.get(row.duplicate_transaction_id)
        matched_duplicate = None
        if duplicate_transaction is not None:
            matched_duplicate = MatchedDuplicateSummary(
                transaction_id=duplicate_transaction.id,
                occurred_at=duplicate_transaction.occurred_at,
                amount=duplicate_transaction.amount,
                currency=duplicate_transaction.currency,
                description=duplicate_transaction.description_raw,
                merchant_name=(
                    duplicate_transaction.merchant.name
                    if duplicate_transaction.merchant is not None
                    else None
                ),
                category_name=(
                    duplicate_transaction.category.name
                    if duplicate_transaction.category is not None
                    else None
                ),
                import_batch_id=duplicate_transaction.import_batch_id,
            )
        payload = row.normalized_payload or {}
        row_responses.append(
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
                proposed_category_id=row.proposed_category_id,
                proposed_category_name=(
                    row.proposed_category.name if row.proposed_category is not None else None
                ),
                proposed_subcategory_id=row.proposed_subcategory_id,
                proposed_subcategory_name=(
                    row.proposed_subcategory.name if row.proposed_subcategory is not None else None
                ),
                proposed_flow_type=row.proposed_flow_type,
                proposed_scope=row.proposed_scope,
                confidence=row.confidence,
                duplicate_transaction_id=(
                    duplicate_transaction.id if duplicate_transaction is not None else None
                ),
                duplicate_of_row_number=payload.get("duplicate_of_row_number"),
                duplicate_included=row.duplicate_included,
                reviewed_uncategorized=row.reviewed_uncategorized,
                reviewed_at=row.reviewed_at,
                matched_duplicate=matched_duplicate,
                error_message=row.error_message,
                normalized_payload=payload,
            )
        )

    return ImportPreviewResponse(
        summary=ImportPreviewSummary(
            import_batch_id=import_batch.id,
            source_filename=import_batch.source_filename,
            status=import_batch.status,
            period_start=import_batch.period_start,
            period_end=import_batch.period_end,
            total_rows=import_batch.total_rows,
            matching_rows_count=(
                total_matching_rows if total_matching_rows is not None else import_batch.total_rows
            ),
            returned_rows=len(row_responses),
            offset=offset,
            limit=limit,
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


def _action_response(db: Session, family_id: UUID, result) -> ImportReviewActionResponse:
    status_counts = _get_status_counts(db, result.batch.id)
    rows = (
        db.scalars(
            select(ImportPreviewRow)
            .options(
                joinedload(ImportPreviewRow.proposed_category),
                joinedload(ImportPreviewRow.proposed_subcategory),
            )
            .where(
                ImportPreviewRow.import_batch_id == result.batch.id,
                ImportPreviewRow.id.in_([row.id for row in result.rows]),
            )
            .order_by(ImportPreviewRow.row_number)
        )
        .unique()
        .all()
    )
    full_response = _to_response(
        db,
        family_id,
        result.batch,
        rows,
        status_counts,
        offset=0,
        limit=max(1, len(rows)),
    )
    return ImportReviewActionResponse(
        requested_count=result.requested_count,
        matched_count=result.matched_count,
        changed_count=result.changed_count,
        summary=ImportReviewSummary(
            import_batch_id=result.batch.id,
            status=result.batch.status,
            total_rows=result.batch.total_rows,
            auto_ready_count=status_counts["auto_ready"],
            needs_review_count=status_counts["needs_review"],
            imported_count=result.batch.imported_count,
            excluded_count=result.batch.excluded_count,
            duplicate_count=result.batch.duplicate_count,
            error_count=result.batch.error_count,
            uncategorized_count=result.batch.uncategorized_count,
            work_fop_count=result.batch.work_fop_count,
            savings_count=result.batch.savings_count,
        ),
        rows=full_response.rows,
    )


def _raise_review_http_error(exc: ImportReviewError) -> None:
    if isinstance(exc, ImportDraftNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ImportReviewValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail="Import review request failed.") from exc


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
