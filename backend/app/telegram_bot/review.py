from __future__ import annotations

import base64
import binascii
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.category import Category
from app.models.transaction import Transaction
from app.telegram_bot.dispatcher import BotReplyContent


REVIEW_NOT_CONFIGURED_TEXT = (
    "Review queue пока не настроена.\n\n"
    "Добавь TELEGRAM_DEFAULT_FAMILY_ID в backend .env, чтобы команда /review знала, "
    "для какой семьи искать операции."
)
REVIEW_INVALID_FAMILY_ID_TEXT = (
    "TELEGRAM_DEFAULT_FAMILY_ID настроен неверно.\n\n"
    "Укажи UUID семьи из demo seed или из базы."
)
REVIEW_EMPTY_TEXT = "Операций на проверку нет."
REVIEW_DONE_USAGE_TEXT = "Используй команду /done <transaction_id> из списка /review."
REVIEW_TRANSACTION_NOT_FOUND_TEXT = "Операция не найдена в текущей семье."
REVIEW_ALREADY_DONE_TEXT = "Эта операция уже отмечена как проверенная."
REVIEW_MARKED_DONE_TEXT = "Операция отмечена как проверенная."
REVIEW_CATEGORIES_EMPTY_TEXT = "Категории пока не найдены."
REVIEW_CATEGORY_USAGE_TEXT = "Не удалось прочитать выбранную категорию."
REVIEW_CATEGORY_NOT_FOUND_TEXT = "Категория не найдена для текущей семьи."
REVIEW_CATEGORY_ASSIGNED_TEXT = "Категория назначена, операция отмечена как проверенная."


def build_review_text(db: Session, family_id_value: str | None, *, limit: int = 5) -> str:
    if family_id_value is None or not family_id_value.strip():
        return REVIEW_NOT_CONFIGURED_TEXT

    family_id = _parse_family_id(family_id_value)
    if family_id is None:
        return REVIEW_INVALID_FAMILY_ID_TEXT

    transactions = _load_review_transactions(db, family_id=family_id, limit=limit)
    return format_review_text(transactions)


def build_review_reply_content(
    db: Session,
    family_id_value: str | None,
    *,
    limit: int = 5,
) -> BotReplyContent:
    if family_id_value is None or not family_id_value.strip():
        return BotReplyContent(text=REVIEW_NOT_CONFIGURED_TEXT)

    family_id = _parse_family_id(family_id_value)
    if family_id is None:
        return BotReplyContent(text=REVIEW_INVALID_FAMILY_ID_TEXT)

    transactions = _load_review_transactions(db, family_id=family_id, limit=limit)
    return BotReplyContent(
        text=format_review_text(transactions),
        reply_markup=_review_reply_markup(transactions),
    )


def mark_reviewed_text(db: Session, family_id_value: str | None, transaction_id_value: str | None) -> str:
    if family_id_value is None or not family_id_value.strip():
        return REVIEW_NOT_CONFIGURED_TEXT

    family_id = _parse_family_id(family_id_value)
    if family_id is None:
        return REVIEW_INVALID_FAMILY_ID_TEXT

    transaction_id = _parse_family_id(transaction_id_value)
    if transaction_id is None:
        return REVIEW_DONE_USAGE_TEXT

    transaction = db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.family_id == family_id,
            Transaction.deleted_at.is_(None),
        )
    )
    if transaction is None:
        return REVIEW_TRANSACTION_NOT_FOUND_TEXT
    if not transaction.needs_review:
        return REVIEW_ALREADY_DONE_TEXT

    transaction.needs_review = False
    db.commit()
    return REVIEW_MARKED_DONE_TEXT


def build_category_menu_content(
    db: Session,
    family_id_value: str | None,
    transaction_id_value: str | None,
    *,
    limit: int = 10,
) -> BotReplyContent:
    family_id = _configured_family_id(family_id_value)
    if isinstance(family_id, str):
        return BotReplyContent(text=family_id)

    transaction_id = _decode_uuid_token(transaction_id_value)
    if transaction_id is None:
        return BotReplyContent(text=REVIEW_TRANSACTION_NOT_FOUND_TEXT)

    transaction = _load_transaction(db, family_id=family_id, transaction_id=transaction_id)
    if transaction is None:
        return BotReplyContent(text=REVIEW_TRANSACTION_NOT_FOUND_TEXT)

    categories = _load_categories(db, family_id=family_id, limit=limit)
    if not categories:
        return BotReplyContent(text=REVIEW_CATEGORIES_EMPTY_TEXT)

    return BotReplyContent(
        text=f"Выбери категорию для операции {transaction.occurred_at:%d.%m.%Y}.",
        reply_markup=_category_reply_markup(transaction, categories),
    )


def assign_category_text(
    db: Session,
    family_id_value: str | None,
    transaction_id_value: str | None,
    category_id_value: str | None,
) -> str:
    family_id = _configured_family_id(family_id_value)
    if isinstance(family_id, str):
        return family_id

    transaction_id = _decode_uuid_token(transaction_id_value)
    category_id = _decode_uuid_token(category_id_value)
    if transaction_id is None or category_id is None:
        return REVIEW_CATEGORY_USAGE_TEXT

    transaction = _load_transaction(db, family_id=family_id, transaction_id=transaction_id)
    if transaction is None:
        return REVIEW_TRANSACTION_NOT_FOUND_TEXT

    category = db.scalar(
        select(Category).where(
            Category.id == category_id,
            or_(Category.family_id == family_id, Category.family_id.is_(None)),
        )
    )
    if category is None:
        return REVIEW_CATEGORY_NOT_FOUND_TEXT

    transaction.category = category
    transaction.needs_review = False
    db.commit()
    return REVIEW_CATEGORY_ASSIGNED_TEXT


def format_review_text(transactions: list[Transaction]) -> str:
    if not transactions:
        return REVIEW_EMPTY_TEXT

    lines = ["Операции на проверку", ""]
    for index, transaction in enumerate(transactions, start=1):
        title = _transaction_title(transaction)
        category_name = transaction.category.name if transaction.category else "без категории"
        lines.append(
            f"{index}. {transaction.occurred_at:%d.%m.%Y} | id: {transaction.id} | "
            f"{_format_money(transaction.amount)} {transaction.currency} | "
            f"{title} | {category_name}"
        )
    return "\n".join(lines)


def _load_review_transactions(db: Session, *, family_id: UUID, limit: int) -> list[Transaction]:
    return db.scalars(
        select(Transaction)
        .options(joinedload(Transaction.merchant), joinedload(Transaction.category))
        .where(
            Transaction.family_id == family_id,
            Transaction.deleted_at.is_(None),
            Transaction.needs_review.is_(True),
        )
        .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
        .limit(limit)
    ).all()


def _load_transaction(db: Session, *, family_id: UUID, transaction_id: UUID) -> Transaction | None:
    return db.scalar(
        select(Transaction)
        .options(joinedload(Transaction.category))
        .where(
            Transaction.id == transaction_id,
            Transaction.family_id == family_id,
            Transaction.deleted_at.is_(None),
        )
    )


def _load_categories(db: Session, *, family_id: UUID, limit: int) -> list[Category]:
    return db.scalars(
        select(Category)
        .where(or_(Category.family_id == family_id, Category.family_id.is_(None)))
        .order_by(Category.is_system.desc(), Category.name)
        .limit(limit)
    ).all()


def _transaction_title(transaction: Transaction) -> str:
    if transaction.merchant:
        return transaction.merchant.name
    if transaction.comment:
        return transaction.comment
    if transaction.description_normalized:
        return transaction.description_normalized
    if transaction.description_raw:
        return transaction.description_raw
    return transaction.flow_type


def _parse_family_id(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _format_money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", " ")


def _configured_family_id(value: str | None) -> UUID | str:
    if value is None or not value.strip():
        return REVIEW_NOT_CONFIGURED_TEXT

    family_id = _parse_family_id(value)
    if family_id is None:
        return REVIEW_INVALID_FAMILY_ID_TEXT
    return family_id


def _review_reply_markup(transactions: list[Transaction]) -> dict[str, list[list[dict[str, str]]]] | None:
    if not transactions:
        return None

    return {
        "inline_keyboard": [
            [
                {
                    "text": f"Готово {index}",
                    "callback_data": f"review_done:{transaction.id}",
                },
                {
                    "text": f"Категория {index}",
                    "callback_data": f"review_categories:{_encode_uuid_token(transaction.id)}",
                },
            ]
            for index, transaction in enumerate(transactions, start=1)
        ]
    }


def _category_reply_markup(
    transaction: Transaction,
    categories: list[Category],
) -> dict[str, list[list[dict[str, str]]]]:
    transaction_token = _encode_uuid_token(transaction.id)
    return {
        "inline_keyboard": [
            [
                {
                    "text": category.name,
                    "callback_data": (
                        f"review_category:{transaction_token}:{_encode_uuid_token(category.id)}"
                    ),
                }
            ]
            for category in categories
        ]
    }


def _encode_uuid_token(value: UUID) -> str:
    return base64.urlsafe_b64encode(value.bytes).decode("ascii").rstrip("=")


def _decode_uuid_token(value: str | None) -> UUID | None:
    if value is None or not value.strip():
        return None
    try:
        padded_value = value + "=" * (-len(value) % 4)
        return UUID(bytes=base64.urlsafe_b64decode(padded_value.encode("ascii")))
    except (binascii.Error, ValueError, TypeError):
        return _parse_family_id(value)
