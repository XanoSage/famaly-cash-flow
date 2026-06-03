from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.summary import TRANSFER_FLOW_TYPES
from app.models.transaction import Transaction


@dataclass(frozen=True)
class SavingsTimelineBucket:
    period: date
    savings: Decimal
    expenses: Decimal
    savings_count: int
    expense_count: int


@dataclass(frozen=True)
class SavingsAnalytics:
    total_savings: Decimal
    total_expenses: Decimal
    savings_count: int
    expense_count: int
    savings_to_expenses_percent: Decimal
    average_daily_savings: Decimal
    projected_yearly_savings: Decimal
    period_days: int
    rows: list[SavingsTimelineBucket]


class SavingsAnalyticsService:
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
    ) -> SavingsAnalytics:
        transactions = self._load_transactions(
            family_id=family_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            account_id=account_id,
            scope=scope,
        )
        buckets: dict[date, _MutableSavingsBucket] = {}
        for transaction in transactions:
            period = transaction.occurred_at.date()
            bucket = buckets.setdefault(period, _MutableSavingsBucket(period=period))
            bucket.add(transaction)

        rows = [bucket.freeze() for _, bucket in sorted(buckets.items(), key=lambda item: item[0])]
        total_savings = sum((row.savings for row in rows), Decimal("0.00"))
        total_expenses = sum((row.expenses for row in rows), Decimal("0.00"))
        period_days = _period_days(rows)
        average_daily_savings = _average_daily_savings(total_savings, period_days)

        return SavingsAnalytics(
            total_savings=total_savings,
            total_expenses=total_expenses,
            savings_count=sum(row.savings_count for row in rows),
            expense_count=sum(row.expense_count for row in rows),
            savings_to_expenses_percent=_percent(total_savings, total_expenses),
            average_daily_savings=average_daily_savings,
            projected_yearly_savings=(average_daily_savings * Decimal(365)).quantize(Decimal("0.01")),
            period_days=period_days,
            rows=rows,
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
            (
                (Transaction.flow_type == "transfer_to_savings")
                | (
                    (Transaction.direction == "expense")
                    & Transaction.flow_type.not_in(TRANSFER_FLOW_TYPES)
                )
            ),
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


@dataclass
class _MutableSavingsBucket:
    period: date
    savings: Decimal = Decimal("0.00")
    expenses: Decimal = Decimal("0.00")
    savings_count: int = 0
    expense_count: int = 0

    def add(self, transaction: Transaction) -> None:
        if transaction.flow_type == "transfer_to_savings":
            self.savings += abs(transaction.amount)
            self.savings_count += 1
            return

        self.expenses += abs(transaction.amount)
        self.expense_count += 1

    def freeze(self) -> SavingsTimelineBucket:
        return SavingsTimelineBucket(
            period=self.period,
            savings=self.savings,
            expenses=self.expenses,
            savings_count=self.savings_count,
            expense_count=self.expense_count,
        )


def _period_days(rows: list[SavingsTimelineBucket]) -> int:
    if not rows:
        return 0
    return max((rows[-1].period - rows[0].period).days + 1, 1)


def _average_daily_savings(total_savings: Decimal, period_days: int) -> Decimal:
    if period_days <= 0:
        return Decimal("0.00")
    return (total_savings / Decimal(period_days)).quantize(Decimal("0.01"))


def _percent(amount: Decimal, total: Decimal) -> Decimal:
    if total == 0:
        return Decimal("0.00")
    return ((amount / total) * Decimal("100")).quantize(Decimal("0.01"))
