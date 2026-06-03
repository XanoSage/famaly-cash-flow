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


class AnalyticsInsightResponse(BaseModel):
    code: str
    title: str
    message: str
    severity: str
    metric_name: str | None
    metric_value: Decimal | None


class AnalyticsInsightsResponse(BaseModel):
    rows: list[AnalyticsInsightResponse]


class SavingsTimelineBucketResponse(BaseModel):
    period: date
    savings: Decimal
    expenses: Decimal
    savings_count: int
    expense_count: int


class SavingsAnalyticsResponse(BaseModel):
    total_savings: Decimal
    total_expenses: Decimal
    savings_count: int
    expense_count: int
    savings_to_expenses_percent: Decimal
    average_daily_savings: Decimal
    projected_yearly_savings: Decimal
    period_days: int
    rows: list[SavingsTimelineBucketResponse]


class AnalyticsDashboardResponse(BaseModel):
    summary: AnalyticsSummaryResponse
    timeline: TimelineAnalyticsResponse
    top_categories: CategoryAnalyticsResponse
    top_merchants: MerchantAnalyticsResponse
    insights: AnalyticsInsightsResponse
