from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.transactions import Scope


class CashWalletResponse(BaseModel):
    id: UUID
    name: str
    currency: str


class CashOperationResponse(BaseModel):
    id: UUID
    occurred_at: datetime
    amount: Decimal
    currency: str
    direction: str
    flow_type: str
    description: str | None
    transfer_group_id: UUID | None
    transfer_role: str | None


class CashSummaryResponse(BaseModel):
    wallet: CashWalletResponse | None
    balance: Decimal
    recent_operations: list[CashOperationResponse]


class CashExpenseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=2)
    occurred_at: datetime | None = None
    merchant_name: str | None = Field(default=None, max_length=255)
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
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


class CashWithdrawalCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_account_id: UUID
    amount: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=2)
    occurred_at: datetime | None = None
    description: str | None = Field(default=None, max_length=255)
    comment: str | None = None

    @field_validator("occurred_at")
    @classmethod
    def require_aware_occurrence(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone offset")
        return value.astimezone(UTC)


class CashWithdrawalResponse(BaseModel):
    transfer_group_id: UUID
    source_transaction_id: UUID
    destination_transaction_id: UUID
    amount: Decimal
    cash_balance: Decimal
