from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class AnalyticsSummaryResponse(BaseModel):
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
