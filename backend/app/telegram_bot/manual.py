from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.user import UserPreference
from app.services.import_review import normalize_review_text
from app.services.transactions import TransactionService, TransactionServiceError
from app.telegram_bot.context import TelegramRequestContext

MANUAL_SELECT_ACCOUNT_TEXT = "Сначала выбери активный счёт командой /account."
MANUAL_PARSE_USAGE_TEXT = "Напиши операцию в формате: АТБ 450 еда"
MANUAL_INCOME_USAGE_TEXT = "Доход добавляется командой: /income 25000 Зарплата"
MANUAL_CASH_USAGE_TEXT = "Наличный расход добавляется командой: /cash 450 Рынок"
MANUAL_CASH_WALLET_MISSING_TEXT = (
    "Сначала создайте семейный кошелёк наличных в веб-разделе «Наличные»."
)
MANUAL_CREATED_TEXT = "Операция добавлена."
MANUAL_CREATED_REVIEW_TEXT = "Операция добавлена и отправлена на проверку."
MANUAL_CASH_CREATED_TEXT = "Расход наличными записан."
MANUAL_CASH_BALANCE_TEXT = "Остаток в кошельке:"

_AMOUNT_PATTERN = re.compile(r"(?<!\w)-?\d+(?:[,.]\d{1,2})?(?!\w)")
_INCOME_PATTERN = re.compile(
    r"^/income(?:@[A-Za-z0-9_]+)?\s+(\d+(?:[,.]\d{1,2})?)\s+(.+?)\s*$",
    flags=re.IGNORECASE,
)
_CASH_PATTERN = re.compile(
    r"^/cash(?:@[A-Za-z0-9_]+)?\s+(\d+(?:[,.]\d{1,2})?)\s+(.+?)\s*$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ManualTransactionDraft:
    description: str
    amount: Decimal
    category_hint: str | None
    direction: str = "expense"
    income_type: str | None = None
    cash_expense: bool = False


def create_manual_transaction_text(
    db: Session,
    *,
    context: TelegramRequestContext,
    text: str,
) -> str:
    account = context.default_account
    draft = parse_manual_transaction(text)
    if draft is None:
        if _is_cash_command(text):
            return MANUAL_CASH_USAGE_TEXT
        return MANUAL_INCOME_USAGE_TEXT if _is_income_command(text) else MANUAL_PARSE_USAGE_TEXT

    if draft.cash_expense:
        service = TransactionService(db)
        try:
            transaction = service.create_cash_expense(
                user=context.user,
                amount=draft.amount,
                merchant_name=draft.description,
                scope="family",
                comment=f"Telegram manual: {text.strip()}",
                raw_text=text,
            )
        except TransactionServiceError as exc:
            if "cash wallet" in str(exc).lower():
                return MANUAL_CASH_WALLET_MISSING_TEXT
            return MANUAL_CASH_USAGE_TEXT
        language = _user_language(db, context.user.id)
        if language == "uk":
            message = "Витрату готівкою записано."
            balance_text = "Залишок у гаманці:"
        else:
            message = MANUAL_CASH_CREATED_TEXT
            balance_text = MANUAL_CASH_BALANCE_TEXT
        balance = service.cash_wallet_balance(user=context.user)
        return f"{message}\n{balance_text} {balance} {transaction.currency}."

    if account is None:
        return MANUAL_SELECT_ACCOUNT_TEXT

    category_id = _find_category_id(
        db,
        family_id=context.family.id,
        hint=draft.category_hint,
    )
    service = TransactionService(db)
    try:
        arguments = {
            "user": context.user,
            "account_id": account.id,
            "amount": draft.amount,
            "occurred_at": None,
            "merchant_name": draft.description,
            "category_id": category_id,
            "scope": "family",
            "comment": f"Telegram manual: {text.strip()}",
            "raw_text": text,
        }
        if draft.direction == "income":
            transaction = service.create_income(
                **arguments,
                income_type=draft.income_type or "income",
            )
        else:
            transaction = service.create_expense(**arguments)
    except TransactionServiceError:
        return MANUAL_SELECT_ACCOUNT_TEXT

    if transaction.needs_review:
        return f"{MANUAL_CREATED_REVIEW_TEXT}\n\n{_format_created_transaction(transaction)}"
    return f"{MANUAL_CREATED_TEXT}\n\n{_format_created_transaction(transaction)}"


def parse_manual_transaction(text: str) -> ManualTransactionDraft | None:
    normalized_text = text.strip()
    if _is_cash_command(normalized_text):
        match = _CASH_PATTERN.fullmatch(normalized_text)
        if match is None:
            return None
        amount = _parse_positive_amount(match.group(1))
        if amount is None:
            return None
        description = match.group(2).strip()
        if not description:
            return None
        return ManualTransactionDraft(
            description=description,
            amount=amount,
            category_hint=None,
            cash_expense=True,
        )
    if _is_income_command(normalized_text):
        match = _INCOME_PATTERN.fullmatch(normalized_text)
        if match is None:
            return None
        amount = _parse_positive_amount(match.group(1))
        if amount is None:
            return None
        description = match.group(2).strip()
        if not description:
            return None
        return ManualTransactionDraft(
            description=description,
            amount=amount,
            category_hint=None,
            direction="income",
            income_type="income",
        )
    if not normalized_text or normalized_text.startswith("/"):
        return None

    match = _AMOUNT_PATTERN.search(normalized_text)
    if match is None:
        return None
    amount = _parse_positive_amount(match.group(0))
    if amount is None:
        return None

    description = normalized_text[: match.start()].strip()
    category_hint = normalized_text[match.end() :].strip()
    if not description:
        description = category_hint or "Ручная операция"
        category_hint = None

    return ManualTransactionDraft(
        description=description,
        amount=amount,
        category_hint=category_hint or None,
    )


def _parse_positive_amount(value: str) -> Decimal | None:
    try:
        amount = Decimal(value.replace(",", "."))
        if not amount.is_finite() or amount <= 0:
            return None
        return amount.quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _is_income_command(text: str) -> bool:
    if not text.strip():
        return False
    command = text.strip().split(maxsplit=1)[0].split("@", maxsplit=1)[0].lower()
    return command == "/income"


def _is_cash_command(text: str) -> bool:
    if not text.strip():
        return False
    command = text.strip().split(maxsplit=1)[0].split("@", maxsplit=1)[0].lower()
    return command == "/cash"


def _user_language(db: Session, user_id) -> str:
    language = db.scalar(select(UserPreference.language).where(UserPreference.user_id == user_id))
    return language or "ru"


def _find_category_id(db: Session, *, family_id, hint: str | None):
    normalized_hint = normalize_review_text(hint)
    if not normalized_hint:
        return None
    categories = db.scalars(
        select(Category).where(or_(Category.family_id == family_id, Category.family_id.is_(None)))
    ).all()
    for category in categories:
        if normalize_review_text(category.name) == normalized_hint:
            return category.id
    for category in categories:
        name = normalize_review_text(category.name)
        if normalized_hint in name or name in normalized_hint:
            return category.id
    return None


def _format_created_transaction(transaction) -> str:
    category_name = transaction.category.name if transaction.category else "без категории"
    return (
        f"{transaction.description_override or transaction.description_normalized}: "
        f"{transaction.amount} {transaction.currency} | {category_name}"
    )
