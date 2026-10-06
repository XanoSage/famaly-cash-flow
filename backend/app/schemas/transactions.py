from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Direction = Literal["expense", "income"]
IncomeType = Literal["income", "refund", "own_transfer", "debt", "other"]
Scope = Literal["family", "personal_main_user", "work_fop"]
MoneyAmount = Decimal


class TransactionResponse(BaseModel):
    id: UUID
    family_id: UUID
    account_id: UUID
    account_name: str
    payment_instrument_id: UUID | None
    payment_instrument_label: str | None
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
    transfer_group_id: UUID | None
    transfer_role: str | None
    income_type: str | None
    scope: str
    description_raw: str | None
    description_normalized: str | None
    description_override: str | None
    display_description: str | None
    bank_category_raw: str | None
    merchant_id: UUID | None
    merchant_name: str | None
    category_id: UUID | None
    category_name: str | None
    subcategory_id: UUID | None
    subcategory_name: str | None
    comment: str | None
    is_cash: bool
    is_duplicate_candidate: bool
    needs_review: bool


class TransactionListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    rows: list[TransactionResponse]


class ManualTransactionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: Direction
    amount: MoneyAmount = Field(gt=Decimal("0"), max_digits=14, decimal_places=2)
    account_id: UUID
    occurred_at: datetime | None = None
    merchant_name: str | None = Field(default=None, max_length=255)
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    flow_type: str | None = Field(default=None, max_length=64)
    income_type: IncomeType | None = None
    scope: Scope = "family"
    comment: str | None = None

    @field_validator("occurred_at")
    @classmethod
    def require_aware_occurrence(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone offset")
        return value.astimezone(UTC)


class TransactionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: UUID | None = None
    occurred_at: datetime | None = None
    amount: MoneyAmount | None = Field(
        default=None,
        gt=Decimal("0"),
        max_digits=14,
        decimal_places=2,
    )
    direction: Direction | None = None
    merchant_name: str | None = Field(default=None, max_length=255)
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    flow_type: str | None = Field(default=None, max_length=64)
    income_type: IncomeType | None = None
    scope: Scope | None = None
    comment: str | None = None
    needs_review: bool | None = None

    @field_validator("occurred_at")
    @classmethod
    def require_aware_occurrence(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone offset")
        return value.astimezone(UTC)
