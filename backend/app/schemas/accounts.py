from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class AccountResponse(BaseModel):
    id: UUID
    name: str
    type: str
    currency: str
    is_active: bool
    owner_user_id: UUID | None
    is_default: bool


class AccountListResponse(BaseModel):
    rows: list[AccountResponse]
