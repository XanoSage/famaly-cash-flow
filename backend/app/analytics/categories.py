from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.analytics.merchants import _share_percent
from app.analytics.summary import TRANSFER_FLOW_TYPES
from app.models.transaction import Transaction

UNCATEGORIZED_KEY = "uncategorized"


@dataclass(frozen=True)
class CategoryAnalyticsRow:
    category_id: UUID | None
    category_name: str
    subcategory_id: UUID | None
    subcategory_name: str | None
    amount: Decimal
    transaction_count: int
    share_percent: Decimal


@dataclass(frozen=True)
class CategoryAnalytics:
    total_amount: Decimal
    total_transactions: int
    rows: list[CategoryAnalyticsRow]


class CategoryAnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build(
        self,
        *,
        family_id: UUID,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        account_id: UUID | None = None,
        scope: str | None = None,
        include_subcategories: bool = False,
        limit: int = 20,
        sort_by: str = "amount",
    ) -> CategoryAnalytics:
        transactions = self._load_expense_transactions(
            family_id=family_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            account_id=account_id,
            scope=scope,
        )
        grouped = _group_by_category(transactions, include_subcategories=include_subcategories)
        total_amount = sum((row.amount for row in grouped), Decimal("0.00"))
        rows_with_share = [
            CategoryAnalyticsRow(
                category_id=row.category_id,
                category_name=row.category_name,
                subcategory_id=row.subcategory_id,
                subcategory_name=row.subcategory_name,
                amount=row.amount,
                transaction_count=row.transaction_count,
                share_percent=_share_percent(row.amount, total_amount),
            )
            for row in grouped
        ]
        sorted_rows = _sort_rows(rows_with_share, sort_by)
        return CategoryAnalytics(
            total_amount=total_amount,
            total_transactions=sum(row.transaction_count for row in grouped),
            rows=sorted_rows[:limit],
        )

    def _load_expense_transactions(
        self,
        *,
        family_id: UUID,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        account_id: UUID | None,
        scope: str | None,
    ) -> list[Transaction]:
        query = (
            select(Transaction)
            .options(
                joinedload(Transaction.category),
                joinedload(Transaction.subcategory),
            )
            .where(
                Transaction.family_id == family_id,
                Transaction.deleted_at.is_(None),
                Transaction.direction == "expense",
                Transaction.flow_type.not_in(TRANSFER_FLOW_TYPES),
            )
        )
        if occurred_from is not None:
            query = query.where(Transaction.occurred_at >= occurred_from)
        if occurred_to is not None:
            query = query.where(Transaction.occurred_at <= occurred_to)
        if account_id is not None:
            query = query.where(Transaction.account_id == account_id)
        if scope is not None:
            query = query.where(Transaction.scope == scope)
        return self.db.scalars(query).all()


def _group_by_category(
    transactions: list[Transaction],
    *,
    include_subcategories: bool,
) -> list[CategoryAnalyticsRow]:
    grouped: dict[tuple[UUID | str | None, UUID | str | None], CategoryAnalyticsRow] = {}
    for transaction in transactions:
        category_id = transaction.category_id
        category_name = transaction.category.name if transaction.category else "Uncategorized"
        subcategory_id = transaction.subcategory_id if include_subcategories else None
        subcategory_name = (
            transaction.subcategory.name
            if include_subcategories and transaction.subcategory
            else None
        )
        group_key = (
            category_id or UNCATEGORIZED_KEY,
            subcategory_id if include_subcategories else None,
        )
        current = grouped.get(group_key)
        amount = abs(transaction.amount)
        if current is None:
            grouped[group_key] = CategoryAnalyticsRow(
                category_id=category_id,
                category_name=category_name,
                subcategory_id=subcategory_id,
                subcategory_name=subcategory_name,
                amount=amount,
                transaction_count=1,
                share_percent=Decimal("0.00"),
            )
            continue
        grouped[group_key] = CategoryAnalyticsRow(
            category_id=current.category_id,
            category_name=current.category_name,
            subcategory_id=current.subcategory_id,
            subcategory_name=current.subcategory_name,
            amount=current.amount + amount,
            transaction_count=current.transaction_count + 1,
            share_percent=Decimal("0.00"),
        )
    return list(grouped.values())


def _sort_rows(rows: list[CategoryAnalyticsRow], sort_by: str) -> list[CategoryAnalyticsRow]:
    if sort_by == "count":
        return sorted(rows, key=lambda item: (item.transaction_count, item.amount), reverse=True)
    return sorted(rows, key=lambda item: (item.amount, item.transaction_count), reverse=True)
