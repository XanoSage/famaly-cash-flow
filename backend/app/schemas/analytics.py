from __future__ import annotations

from datetime import date
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


class MerchantAnalyticsRowResponse(BaseModel):
    merchant_id: str
    merchant_name: str
    merchant_type: str
    amount: Decimal
    transaction_count: int
    share_percent: Decimal


class MerchantAnalyticsResponse(BaseModel):
    total_amount: Decimal
    total_transactions: int
    rows: list[MerchantAnalyticsRowResponse]


class CategoryAnalyticsRowResponse(BaseModel):
    category_id: str | None
    category_name: str
    subcategory_id: str | None
    subcategory_name: str | None
    amount: Decimal
    transaction_count: int
    share_percent: Decimal


class CategoryAnalyticsResponse(BaseModel):
    total_amount: Decimal
    total_transactions: int
    rows: list[CategoryAnalyticsRowResponse]


class TimelineBucketResponse(BaseModel):
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


class TimelineAnalyticsResponse(BaseModel):
    granularity: str
    rows: list[TimelineBucketResponse]


class AnalyticsDashboardResponse(BaseModel):
    summary: AnalyticsSummaryResponse
    timeline: TimelineAnalyticsResponse
    top_categories: CategoryAnalyticsResponse
    top_merchants: MerchantAnalyticsResponse
