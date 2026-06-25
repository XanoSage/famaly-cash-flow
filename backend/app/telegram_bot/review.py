from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.transaction import Transaction


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


def build_review_text(db: Session, family_id_value: str | None, *, limit: int = 5) -> str:
    if family_id_value is None or not family_id_value.strip():
        return REVIEW_NOT_CONFIGURED_TEXT

    family_id = _parse_family_id(family_id_value)
    if family_id is None:
        return REVIEW_INVALID_FAMILY_ID_TEXT

    transactions = _load_review_transactions(db, family_id=family_id, limit=limit)
    return format_review_text(transactions)


def format_review_text(transactions: list[Transaction]) -> str:
    if not transactions:
        return REVIEW_EMPTY_TEXT

    lines = ["Операции на проверку", ""]
    for index, transaction in enumerate(transactions, start=1):
        title = _transaction_title(transaction)
        category_name = transaction.category.name if transaction.category else "без категории"
        lines.append(
            f"{index}. {transaction.occurred_at:%d.%m.%Y} | "
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
