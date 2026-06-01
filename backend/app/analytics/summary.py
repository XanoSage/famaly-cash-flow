from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction

TRANSFER_FLOW_TYPES = {
    "transfer_to_own_account",
    "transfer_to_savings",
    "transfer_to_wife",
    "person_transfer",
}


@dataclass(frozen=True)
class AnalyticsSummary:
    income: Decimal
    expenses: Decimal
    savings: Decimal
    transfers: Decimal
    net_cash_flow: Decimal
    average_daily_expense: Decimal
    transaction_count: int
    expense_count: int
    income_count: int
    savings_count: int
    transfer_count: int
    needs_review_count: int
    uncategorized_count: int
    work_fop_count: int


class AnalyticsSummaryService:
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
    ) -> AnalyticsSummary:
        transactions = self._load_transactions(
            family_id=family_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            account_id=account_id,
            scope=scope,
        )

        income_transactions = [item for item in transactions if item.direction == "income"]
        saving_transactions = [item for item in transactions if item.flow_type == "transfer_to_savings"]
        transfer_transactions = [
            item
            for item in transactions
            if item.flow_type in TRANSFER_FLOW_TYPES and item.flow_type != "transfer_to_savings"
        ]
        expense_transactions = [
            item
            for item in transactions
            if item.direction == "expense" and item.flow_type not in TRANSFER_FLOW_TYPES
        ]

        income = _sum_positive(income_transactions)
        expenses = _sum_abs(expense_transactions)
        savings = _sum_abs(saving_transactions)
        transfers = _sum_abs(transfer_transactions)

        return AnalyticsSummary(
            income=income,
            expenses=expenses,
            savings=savings,
            transfers=transfers,
            net_cash_flow=income - expenses - savings,
            average_daily_expense=_average_daily_expense(expenses, expense_transactions),
            transaction_count=len(transactions),
            expense_count=len(expense_transactions),
            income_count=len(income_transactions),
            savings_count=len(saving_transactions),
            transfer_count=len(transfer_transactions),
            needs_review_count=sum(item.needs_review for item in transactions),
            uncategorized_count=sum(item.category_id is None for item in expense_transactions),
            work_fop_count=sum(item.scope == "work_fop" for item in transactions),
        )

    def _load_transactions(
        self,
        *,
        family_id: UUID,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        account_id: UUID | None,
        scope: str | None,
    ) -> list[Transaction]:
        query = select(Transaction).where(
            Transaction.family_id == family_id,
            Transaction.deleted_at.is_(None),
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


def _sum_abs(transactions: list[Transaction]) -> Decimal:
    return sum((abs(item.amount) for item in transactions), Decimal("0.00"))


def _sum_positive(transactions: list[Transaction]) -> Decimal:
    return sum((item.amount for item in transactions if item.amount > 0), Decimal("0.00"))


def _average_daily_expense(expenses: Decimal, expense_transactions: list[Transaction]) -> Decimal:
    if not expense_transactions:
        return Decimal("0.00")
    dates = {item.occurred_at.date() for item in expense_transactions}
    if not dates:
        return Decimal("0.00")
    return (expenses / Decimal(len(dates))).quantize(Decimal("0.01"))
