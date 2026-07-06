from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.telegram_bot.client import TelegramApiError, send_bot_replies
from app.telegram_bot.dispatcher import dispatch_update
from app.telegram_bot.manual import create_manual_transaction_text
from app.telegram_bot.review import (
    assign_category_text,
    build_category_menu_content,
    build_review_reply_content,
    mark_reviewed_text,
)
from app.telegram_bot.summary import build_summary_text

router = APIRouter(prefix="/telegram")


class TelegramWebhookResponse(BaseModel):
    ok: bool


@router.post("/webhook", response_model=TelegramWebhookResponse)
def telegram_webhook(
    update: dict[str, Any],
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> TelegramWebhookResponse:
    if settings.telegram_webhook_secret_token:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret_token:
            raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")

    replies = dispatch_update(
        update,
        summary_text_provider=lambda: build_summary_text(
            db,
            settings.telegram_default_family_id,
        ),
        review_text_provider=lambda: build_review_reply_content(
            db,
            settings.telegram_default_family_id,
        ),
        review_done_text_provider=lambda transaction_id: mark_reviewed_text(
            db,
            settings.telegram_default_family_id,
            transaction_id,
        ),
        review_categories_text_provider=lambda transaction_id: build_category_menu_content(
            db,
            settings.telegram_default_family_id,
            transaction_id,
        ),
        review_category_text_provider=lambda transaction_id, category_id: assign_category_text(
            db,
            settings.telegram_default_family_id,
            transaction_id,
            category_id,
        ),
        text_message_provider=lambda text: create_manual_transaction_text(
            db,
            family_id_value=settings.telegram_default_family_id,
            account_id_value=settings.telegram_default_account_id,
            text=text,
        ),
    )
    try:
        send_bot_replies(settings.telegram_bot_token, replies)
    except TelegramApiError as exc:
        raise HTTPException(status_code=502, detail="Telegram API call failed") from exc

    return TelegramWebhookResponse(ok=True)
