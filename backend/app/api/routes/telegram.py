from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.telegram_bot.dispatcher import dispatch_update

router = APIRouter(prefix="/telegram")


class TelegramWebhookResponse(BaseModel):
    ok: bool


@router.post("/webhook", response_model=TelegramWebhookResponse)
def telegram_webhook(
    update: dict[str, Any],
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> TelegramWebhookResponse:
    if settings.telegram_webhook_secret_token:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret_token:
            raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")

    # Outgoing Telegram API calls will be added after command handlers are covered by tests.
    dispatch_update(update)
    return TelegramWebhookResponse(ok=True)
