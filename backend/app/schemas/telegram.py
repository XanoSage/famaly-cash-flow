from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TelegramLinkTokenResponse(BaseModel):
    token: str
    expires_at: datetime
    telegram_url: str | None


class TelegramLinkStatusResponse(BaseModel):
    is_linked: bool
    username: str | None = None
    first_name: str | None = None
    linked_at: datetime | None = None
