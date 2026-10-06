from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.telegram_identity import TelegramIdentity
from app.models.user import User
from app.schemas.telegram import TelegramLinkStatusResponse, TelegramLinkTokenResponse
from app.services.telegram_linking import (
    TelegramAlreadyLinkedError,
    consume_telegram_link_token,
    create_telegram_link,
    get_active_telegram_identity,
    unlink_telegram_identity,
)
from app.telegram_bot.accounts import build_account_selection, select_default_account_text
from app.telegram_bot.client import TelegramApiError, send_bot_replies
from app.telegram_bot.context import (
    LINK_FAILURE_TEXT,
    resolve_telegram_context,
)
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
TELEGRAM_LINKED_TEXT = "Telegram связан с Family Cash Flow. Теперь доступны финансовые команды."


class TelegramWebhookResponse(BaseModel):
    ok: bool


@router.post(
    "/link-token",
    response_model=TelegramLinkTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_link_token(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TelegramLinkTokenResponse:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        link = create_telegram_link(
            db,
            user_id=current_user.id,
            bot_username=settings.telegram_bot_username,
        )
    except TelegramAlreadyLinkedError as exc:
        raise HTTPException(
            status_code=409, detail="Unlink the current Telegram account first."
        ) from exc
    return TelegramLinkTokenResponse(
        token=link.token,
        expires_at=link.expires_at,
        telegram_url=link.telegram_url,
    )


@router.get("/link-status", response_model=TelegramLinkStatusResponse)
def get_link_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TelegramLinkStatusResponse:
    identity = get_active_telegram_identity(db, user_id=current_user.id)
    return _link_status_response(identity)


@router.delete("/link", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    unlink_telegram_identity(db, user_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/webhook", response_model=TelegramWebhookResponse)
def telegram_webhook(
    update: dict[str, Any],
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> TelegramWebhookResponse:
    configured_secret = settings.telegram_webhook_secret_token
    if configured_secret and (
        x_telegram_bot_api_secret_token is None
        or not secrets.compare_digest(x_telegram_bot_api_secret_token, configured_secret)
    ):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")

    replies = dispatch_update(
        update,
        context_resolver=lambda telegram_user_id, private_chat_id, profile: (
            resolve_telegram_context(
                db,
                telegram_user_id=telegram_user_id,
                private_chat_id=private_chat_id,
                profile=profile,
            )
        ),
        link_text_provider=lambda raw_token, telegram_user_id, private_chat_id, profile: (
            TELEGRAM_LINKED_TEXT
            if consume_telegram_link_token(
                db,
                raw_token=raw_token,
                telegram_user_id=telegram_user_id,
                private_chat_id=private_chat_id,
                profile=profile,
            )
            else LINK_FAILURE_TEXT
        ),
        summary_text_provider=lambda context: build_summary_text(db, context.family.id),
        review_text_provider=lambda context: build_review_reply_content(db, context.family.id),
        review_done_text_provider=lambda context, transaction_id: mark_reviewed_text(
            db,
            context.family.id,
            transaction_id,
            context.user,
        ),
        review_categories_text_provider=lambda context, transaction_id: build_category_menu_content(
            db,
            context.family.id,
            transaction_id,
        ),
        review_category_text_provider=lambda context, transaction_id, category_id: (
            assign_category_text(
                db,
                context.family.id,
                transaction_id,
                category_id,
                context.user,
            )
        ),
        account_text_provider=lambda context: build_account_selection(db, context),
        account_select_text_provider=lambda context, account_id: select_default_account_text(
            db,
            context,
            account_id,
        ),
        text_message_provider=lambda context, text: create_manual_transaction_text(
            db,
            context=context,
            text=text,
        ),
    )
    db.commit()
    try:
        send_bot_replies(settings.telegram_bot_token, replies)
    except TelegramApiError as exc:
        raise HTTPException(status_code=502, detail="Telegram API call failed") from exc

    return TelegramWebhookResponse(ok=True)


def _link_status_response(identity: TelegramIdentity | None) -> TelegramLinkStatusResponse:
    if identity is None:
        return TelegramLinkStatusResponse(is_linked=False)
    return TelegramLinkStatusResponse(
        is_linked=True,
        username=identity.username,
        first_name=identity.first_name,
        linked_at=identity.linked_at,
    )
