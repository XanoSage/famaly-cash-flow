from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.services.account_preferences import AccountPreferenceService, DefaultAccountError
from app.telegram_bot.context import TelegramRequestContext
from app.telegram_bot.dispatcher import BotReplyContent

ACCOUNT_LIST_EMPTY_TEXT = "В этой семье нет активных счетов."
ACCOUNT_NOT_FOUND_TEXT = "Не удалось выбрать этот счёт. Обнови список командой /account."
ACCOUNT_SELECTED_TEXT = "Счёт для ручных операций обновлён."


def build_account_selection(db: Session, context: TelegramRequestContext) -> BotReplyContent:
    accounts = AccountPreferenceService(db).list_active(family_id=context.family.id)
    if not accounts:
        return BotReplyContent(text=ACCOUNT_LIST_EMPTY_TEXT)

    current_id = context.default_account.id if context.default_account else None
    lines = ["Выбери счёт для новых ручных операций:", ""]
    buttons: list[list[dict[str, str]]] = []
    for account in accounts:
        marker = " ✓" if account.id == current_id else ""
        lines.append(f"{account.name}{marker} · {account.currency}")
        buttons.append(
            [
                {
                    "text": f"{account.name}{marker}",
                    "callback_data": f"account_set:{account.id}",
                }
            ]
        )
    return BotReplyContent(
        text="\n".join(lines),
        reply_markup={"inline_keyboard": buttons},
    )


def select_default_account_text(
    db: Session,
    context: TelegramRequestContext,
    account_id_value: str | None,
) -> str:
    try:
        account_id = UUID(account_id_value or "")
        AccountPreferenceService(db).set_default(
            user_id=context.user.id,
            family_id=context.family.id,
            account_id=account_id,
        )
    except (ValueError, DefaultAccountError):
        return ACCOUNT_NOT_FOUND_TEXT
    return ACCOUNT_SELECTED_TEXT
