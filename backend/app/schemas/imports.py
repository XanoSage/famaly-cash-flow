from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ImportPreviewSummary(BaseModel):
    import_batch_id: UUID
    source_filename: str
    status: str
    period_start: datetime | None
    period_end: datetime | None
    total_rows: int
    returned_rows: int
    auto_ready_count: int
    needs_review_count: int
    imported_count: int
    excluded_count: int
    duplicate_count: int
    error_count: int
    uncategorized_count: int
    work_fop_count: int
    savings_count: int
    parser_version: str
    mapping_version: str
    expires_at: datetime | None


class ImportPreviewRowResponse(BaseModel):
    id: UUID
    row_number: int
    status: str
    reason_codes: list[str]
    occurred_at: datetime | None
    amount: Decimal | None
    currency: str | None
    transaction_amount: Decimal | None
    transaction_currency: str | None
    balance_after: Decimal | None
    payment_instrument_label: str | None
    bank_category_raw: str | None
    description_raw: str | None
    merchant_name: str | None
    proposed_flow_type: str | None
    proposed_scope: str | None
    confidence: Decimal | None
    error_message: str | None
    normalized_payload: dict[str, Any]


class ImportPreviewResponse(BaseModel):
    summary: ImportPreviewSummary
    rows: list[ImportPreviewRowResponse]
