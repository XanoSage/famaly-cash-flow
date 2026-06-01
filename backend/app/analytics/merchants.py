from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.analytics.summary import TRANSFER_FLOW_TYPES
from app.models.transaction import Transaction


@dataclass(frozen=True)
class MerchantAnalyticsRow:
    merchant_id: UUID
    merchant_name: str
    merchant_type: str
    amount: Decimal
    transaction_count: int
    share_percent: Decimal


@dataclass(frozen=True)
class MerchantAnalytics:
    total_amount: Decimal
    total_transactions: int
    rows: list[MerchantAnalyticsRow]


class MerchantAnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build(
        self,
        *,
        family_id: UUID,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        account_id: UUID | None = None,
        category_id: UUID | None = None,
        scope: str | None = None,
        limit: int = 10,
        sort_by: str = "amount",
    ) -> MerchantAnalytics:
        transactions = self._load_expense_transactions(
            family_id=family_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            account_id=account_id,
            category_id=category_id,
            scope=scope,
        )
        grouped = _group_by_merchant(transactions)
        total_amount = sum((row.amount for row in grouped), Decimal("0.00"))
        rows_with_share = [
            MerchantAnalyticsRow(
                merchant_id=row.merchant_id,
                merchant_name=row.merchant_name,
                merchant_type=row.merchant_type,
                amount=row.amount,
                transaction_count=row.transaction_count,
                share_percent=_share_percent(row.amount, total_amount),
            )
            for row in grouped
        ]
        sorted_rows = _sort_rows(rows_with_share, sort_by)
        return MerchantAnalytics(
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
        category_id: UUID | None,
        scope: str | None,
    ) -> list[Transaction]:
        query = (
            select(Transaction)
            .options(joinedload(Transaction.merchant))
            .where(
                Transaction.family_id == family_id,
                Transaction.deleted_at.is_(None),
                Transaction.merchant_id.is_not(None),
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
        if category_id is not None:
            query = query.where(Transaction.category_id == category_id)
        if scope is not None:
            query = query.where(Transaction.scope == scope)
        return self.db.scalars(query).all()


def _group_by_merchant(transactions: list[Transaction]) -> list[MerchantAnalyticsRow]:
    grouped: dict[UUID, MerchantAnalyticsRow] = {}
    for transaction in transactions:
        if not transaction.merchant:
            continue
        current = grouped.get(transaction.merchant_id)
        amount = abs(transaction.amount)
        if current is None:
            grouped[transaction.merchant_id] = MerchantAnalyticsRow(
                merchant_id=transaction.merchant.id,
                merchant_name=transaction.merchant.name,
                merchant_type=transaction.merchant.merchant_type,
                amount=amount,
                transaction_count=1,
                share_percent=Decimal("0.00"),
            )
            continue
        grouped[transaction.merchant_id] = MerchantAnalyticsRow(
            merchant_id=current.merchant_id,
            merchant_name=current.merchant_name,
            merchant_type=current.merchant_type,
            amount=current.amount + amount,
            transaction_count=current.transaction_count + 1,
            share_percent=Decimal("0.00"),
        )
    return list(grouped.values())


def _sort_rows(rows: list[MerchantAnalyticsRow], sort_by: str) -> list[MerchantAnalyticsRow]:
    if sort_by == "count":
        return sorted(rows, key=lambda item: (item.transaction_count, item.amount), reverse=True)
    return sorted(rows, key=lambda item: (item.amount, item.transaction_count), reverse=True)


def _share_percent(amount: Decimal, total_amount: Decimal) -> Decimal:
    if total_amount == 0:
        return Decimal("0.00")
    return ((amount / total_amount) * Decimal("100")).quantize(Decimal("0.01"))
