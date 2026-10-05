from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ImportPreviewSummary(BaseModel):
    import_batch_id: UUID
    source_filename: str
    status: str
    period_start: datetime | None
    period_end: datetime | None
    total_rows: int
    matching_rows_count: int
    returned_rows: int
    offset: int
    limit: int
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


class MatchedDuplicateSummary(BaseModel):
    transaction_id: UUID
    occurred_at: datetime
    amount: Decimal
    currency: str
    description: str | None
    merchant_name: str | None
    category_name: str | None
    import_batch_id: UUID | None


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
    proposed_category_id: UUID | None
    proposed_category_name: str | None
    proposed_subcategory_id: UUID | None
    proposed_subcategory_name: str | None
    proposed_flow_type: str | None
    proposed_scope: str | None
    confidence: Decimal | None
    duplicate_transaction_id: UUID | None
    duplicate_of_row_number: int | None
    duplicate_included: bool
    reviewed_uncategorized: bool
    reviewed_at: datetime | None
    matched_duplicate: MatchedDuplicateSummary | None
    error_message: str | None
    normalized_payload: dict[str, Any]


class ImportReviewSummary(BaseModel):
    import_batch_id: UUID
    status: str
    total_rows: int
    auto_ready_count: int
    needs_review_count: int
    imported_count: int
    excluded_count: int
    duplicate_count: int
    error_count: int
    uncategorized_count: int
    work_fop_count: int
    savings_count: int


FlowType = Literal[
    "purchase",
    "cash_withdrawal",
    "cash_expense",
    "transfer_to_own_account",
    "transfer_to_savings",
    "transfer_to_wife",
    "person_transfer",
    "requisites_payment",
    "refund",
    "income",
    "subscription",
    "work_fop",
    "other",
]
Scope = Literal["family", "personal_main_user", "work_fop"]


class ImportPreviewRowPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_category_id: UUID | None = None
    proposed_subcategory_id: UUID | None = None
    proposed_flow_type: FlowType | None = None
    proposed_scope: Scope | None = None
    merchant_name: str | None = Field(default=None, max_length=255)
    excluded: bool | None = None
    include_duplicate: bool | None = None
    accept_uncategorized: bool | None = None
    save_rule: bool = False
    apply_to_merchant: bool = False


BulkAction = Literal[
    "assign_category",
    "set_scope",
    "set_flow_type",
    "exclude",
    "include_duplicate",
    "mark_uncategorized",
    "apply_correction",
]


class ImportBulkActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: BulkAction
    row_ids: list[UUID] = Field(min_length=1, max_length=200)
    proposed_category_id: UUID | None = None
    proposed_subcategory_id: UUID | None = None
    proposed_flow_type: FlowType | None = None
    proposed_scope: Scope | None = None
    merchant_name: str | None = Field(default=None, max_length=255)
    save_rule: bool = False
    apply_to_merchant: bool = False


class ImportReviewActionResponse(BaseModel):
    requested_count: int
    matched_count: int
    changed_count: int
    summary: ImportReviewSummary
    rows: list[ImportPreviewRowResponse]


class ImportPreviewResponse(BaseModel):
    summary: ImportPreviewSummary
    rows: list[ImportPreviewRowResponse]


class ConfirmImportResponse(BaseModel):
    import_batch_id: UUID
    status: str
    created_transactions: int
    excluded_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0
    uncategorized_count: int = 0
    work_fop_count: int = 0
    savings_count: int = 0
