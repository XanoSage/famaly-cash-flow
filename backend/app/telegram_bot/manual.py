from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.category import Category
from app.models.merchant import Merchant
from app.models.transaction import Transaction


MANUAL_NOT_CONFIGURED_TEXT = (
    "Ручное добавление пока не настроено.\n\n"
    "Добавь TELEGRAM_DEFAULT_FAMILY_ID и TELEGRAM_DEFAULT_ACCOUNT_ID в backend .env."
)
MANUAL_INVALID_CONFIG_TEXT = "TELEGRAM_DEFAULT_FAMILY_ID или TELEGRAM_DEFAULT_ACCOUNT_ID настроен неверно."
MANUAL_ACCOUNT_NOT_FOUND_TEXT = "Счёт для ручных операций не найден в текущей семье."
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
    family_id_value: str | None,
    account_id_value: str | None,
    text: str,
) -> str:
    family_id = _parse_uuid(family_id_value)
    account_id = _parse_uuid(account_id_value)
    if not family_id_value or not account_id_value:
        return MANUAL_NOT_CONFIGURED_TEXT
    if family_id is None or account_id is None:
        return MANUAL_INVALID_CONFIG_TEXT

    account = db.scalar(
        select(Account).where(
            Account.id == account_id,
            Account.family_id == family_id,
            Account.is_active.is_(True),
        )
    )
    if account is None:
        return MANUAL_ACCOUNT_NOT_FOUND_TEXT

    draft = parse_manual_transaction(text)
    if draft is None:
        return MANUAL_PARSE_USAGE_TEXT

    category = _find_category(db, family_id=family_id, hint=draft.category_hint)
    merchant = _get_or_create_merchant(db, family_id=family_id, name=draft.description)
    needs_review = category is None

    transaction = Transaction(
        family_id=family_id,
        account_id=account_id,
        occurred_at=datetime.now(),
        amount=-abs(draft.amount),
        currency=account.currency,
        direction="expense",
        flow_type="purchase",
        scope="family",
        description_raw=text.strip(),
        description_normalized=draft.description,
        merchant=merchant,
        category=category,
        comment=f"Telegram manual: {text.strip()}",
        needs_review=needs_review,
    )
    db.add(transaction)
    db.commit()

    if needs_review:
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


def _find_category(db: Session, *, family_id: UUID, hint: str | None) -> Category | None:
    if not hint:
        return None
    normalized_hint = hint.casefold()
    categories = db.scalars(
        select(Category).where(
            (Category.family_id == family_id) | (Category.family_id.is_(None)),
        )
    ).all()
    for category in categories:
        if category.name.casefold() == normalized_hint:
            return category
    for category in categories:
        if normalized_hint in category.name.casefold() or category.name.casefold() in normalized_hint:
            return category
    return None


def _get_or_create_merchant(db: Session, *, family_id: UUID, name: str) -> Merchant:
    normalized_name = name.casefold()
    merchant = db.scalar(
        select(Merchant).where(
            Merchant.family_id == family_id,
            Merchant.normalized_name == normalized_name,
        )
    )
    if merchant is not None:
        return merchant

    merchant = Merchant(
        family_id=family_id,
        name=name,
        normalized_name=normalized_name,
        merchant_type="manual",
    )
    db.add(merchant)
    db.flush()
    return merchant


def _parse_uuid(value: str | None) -> UUID | None:
    if value is None or not value.strip():
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _format_created_transaction(transaction: Transaction) -> str:
    category_name = transaction.category.name if transaction.category else "без категории"
    return f"{transaction.description_normalized}: {transaction.amount} {transaction.currency} | {category_name}"
