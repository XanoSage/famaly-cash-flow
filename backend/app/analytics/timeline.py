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
class TimelineBucket:
    period: date
    income: Decimal
    expenses: Decimal
    savings: Decimal
    transfers: Decimal
    net_cash_flow: Decimal
    transaction_count: int
    expense_count: int
    income_count: int
    savings_count: int
    transfer_count: int


@dataclass(frozen=True)
class TimelineAnalytics:
    granularity: str
    rows: list[TimelineBucket]


class TimelineAnalyticsService:
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
        granularity: str = "day",
    ) -> TimelineAnalytics:
        transactions = self._load_transactions(
            family_id=family_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            account_id=account_id,
            scope=scope,
        )

        if granularity != "day":
            raise ValueError("Only day granularity is supported")

        buckets: dict[date, _MutableTimelineBucket] = {}
        for transaction in transactions:
            period = transaction.occurred_at.date()
            bucket = buckets.setdefault(period, _MutableTimelineBucket(period=period))
            bucket.add(transaction)

        rows = [bucket.freeze() for _, bucket in sorted(buckets.items(), key=lambda item: item[0])]
        return TimelineAnalytics(granularity=granularity, rows=rows)

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


@dataclass
class _MutableTimelineBucket:
    period: date
    income: Decimal = Decimal("0.00")
    expenses: Decimal = Decimal("0.00")
    savings: Decimal = Decimal("0.00")
    transfers: Decimal = Decimal("0.00")
    transaction_count: int = 0
    expense_count: int = 0
    income_count: int = 0
    savings_count: int = 0
    transfer_count: int = 0

    def add(self, transaction: Transaction) -> None:
        self.transaction_count += 1

        if transaction.direction == "income" and transaction.amount > 0:
            self.income += transaction.amount
            self.income_count += 1
            return

        if transaction.flow_type == "transfer_to_savings":
            self.savings += abs(transaction.amount)
            self.savings_count += 1
            return

        if transaction.flow_type in TRANSFER_FLOW_TYPES:
            self.transfers += abs(transaction.amount)
            self.transfer_count += 1
            return

        if transaction.direction == "expense":
            self.expenses += abs(transaction.amount)
            self.expense_count += 1

    def freeze(self) -> TimelineBucket:
        return TimelineBucket(
            period=self.period,
            income=self.income,
            expenses=self.expenses,
            savings=self.savings,
            transfers=self.transfers,
            net_cash_flow=self.income - self.expenses - self.savings,
            transaction_count=self.transaction_count,
            expense_count=self.expense_count,
            income_count=self.income_count,
            savings_count=self.savings_count,
            transfer_count=self.transfer_count,
        )
