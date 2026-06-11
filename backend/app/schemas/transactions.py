from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class TransactionResponse(BaseModel):
    id: UUID
    family_id: UUID
    account_id: UUID
    payment_instrument_id: UUID | None
    owner_user_id: UUID | None
    import_batch_id: UUID | None
    occurred_at: datetime
    amount: Decimal
    currency: str
    transaction_amount: Decimal | None
    transaction_currency: str | None
    balance_after: Decimal | None
    direction: str
    flow_type: str
    income_type: str | None
    scope: str
    description_raw: str | None
    description_normalized: str | None
    bank_category_raw: str | None
    merchant_id: UUID | None
    merchant_name: str | None
    category_id: UUID | None
    category_name: str | None
    subcategory_id: UUID | None
    comment: str | None
    is_cash: bool
    is_duplicate_candidate: bool
    needs_review: bool


class TransactionListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    rows: list[TransactionResponse]
