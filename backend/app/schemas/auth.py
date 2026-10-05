from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def email_has_address_shape(cls, value: str) -> str:
        normalized = value.strip()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Enter a valid email address.")
        return normalized


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CurrentUserResponse(BaseModel):
    id: UUID
    display_name: str
    email: str
    language: str
    family_id: UUID
    family_name: str
