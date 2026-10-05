from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.services.manual_transaction import ManualTransactionError, ManualTransactionService
from app.telegram_bot.context import TelegramRequestContext

MANUAL_SELECT_ACCOUNT_TEXT = "Сначала выбери активный счёт командой /account."
MANUAL_PARSE_USAGE_TEXT = "Напиши операцию в формате: АТБ 450 еда"
MANUAL_CREATED_TEXT = "Операция добавлена."
MANUAL_CREATED_REVIEW_TEXT = "Операция добавлена и отправлена на проверку."

_AMOUNT_PATTERN = re.compile(r"(?<!\w)-?\d+(?:[,.]\d{1,2})?(?!\w)")


@dataclass(frozen=True)
class ManualTransactionDraft:
    description: str
    amount: Decimal
    category_hint: str | None


def create_manual_transaction_text(
    db: Session,
    *,
    context: TelegramRequestContext,
    text: str,
) -> str:
    account = context.default_account
    if account is None:
        return MANUAL_SELECT_ACCOUNT_TEXT

    draft = parse_manual_transaction(text)
    if draft is None:
        return MANUAL_PARSE_USAGE_TEXT

    try:
        transaction = ManualTransactionService(db).create_expense(
            user_id=context.user.id,
            family_id=context.family.id,
            account_id=account.id,
            description=draft.description,
            raw_text=text,
            amount=draft.amount,
            category_hint=draft.category_hint,
        )
    except ManualTransactionError:
        return MANUAL_SELECT_ACCOUNT_TEXT

    if transaction.needs_review:
        return f"{MANUAL_CREATED_REVIEW_TEXT}\n\n{_format_created_transaction(transaction)}"
    return f"{MANUAL_CREATED_TEXT}\n\n{_format_created_transaction(transaction)}"


def parse_manual_transaction(text: str) -> ManualTransactionDraft | None:
    normalized_text = text.strip()
    if not normalized_text or normalized_text.startswith("/"):
        return None

    match = _AMOUNT_PATTERN.search(normalized_text)
    if match is None:
        return None

    try:
        amount = Decimal(match.group(0).replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    if amount == Decimal("0.00"):
        return None

    description = normalized_text[: match.start()].strip()
    category_hint = normalized_text[match.end() :].strip()
    if not description:
        description = category_hint or "Ручная операция"
        category_hint = None

    return ManualTransactionDraft(
        description=description,
        amount=abs(amount),
        category_hint=category_hint or None,
    )


def _format_created_transaction(transaction) -> str:
    category_name = transaction.category.name if transaction.category else "без категории"
    return (
        f"{transaction.description_normalized}: {transaction.amount} "
        f"{transaction.currency} | {category_name}"
    )
