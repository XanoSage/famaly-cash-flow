from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics.categories import CategoryAnalyticsService
from app.analytics.merchants import MerchantAnalyticsService
from app.analytics.summary import AnalyticsSummaryService
from app.analytics.timeline import TimelineAnalyticsService
from app.db.session import get_db
from app.schemas.analytics import (
    AnalyticsDashboardResponse,
    AnalyticsSummaryResponse,
    CategoryAnalyticsResponse,
    CategoryAnalyticsRowResponse,
    MerchantAnalyticsResponse,
    MerchantAnalyticsRowResponse,
    TimelineAnalyticsResponse,
    TimelineBucketResponse,
)

router = APIRouter(prefix="/analytics")


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_analytics_summary(
    family_id: UUID = Query(...),
    occurred_from: datetime | None = Query(None),
    occurred_to: datetime | None = Query(None),
    account_id: UUID | None = Query(None),
    scope: str | None = Query(None),
    db: Session = Depends(get_db),
) -> AnalyticsSummaryResponse:
    summary = AnalyticsSummaryService(db).build(
        family_id=family_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        account_id=account_id,
        scope=scope,
    )
    return _summary_response(summary)


@router.get("/by-merchant", response_model=MerchantAnalyticsResponse)
def get_analytics_by_merchant(
    family_id: UUID = Query(...),
    occurred_from: datetime | None = Query(None),
    occurred_to: datetime | None = Query(None),
    account_id: UUID | None = Query(None),
    category_id: UUID | None = Query(None),
    scope: str | None = Query(None),
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("amount", pattern="^(amount|count)$"),
    db: Session = Depends(get_db),
) -> MerchantAnalyticsResponse:
    analytics = MerchantAnalyticsService(db).build(
        family_id=family_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        account_id=account_id,
        category_id=category_id,
        scope=scope,
        limit=limit,
        sort_by=sort_by,
    )
    return _merchant_response(analytics)


@router.get("/by-category", response_model=CategoryAnalyticsResponse)
def get_analytics_by_category(
    family_id: UUID = Query(...),
    occurred_from: datetime | None = Query(None),
    occurred_to: datetime | None = Query(None),
    account_id: UUID | None = Query(None),
    scope: str | None = Query(None),
    include_subcategories: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("amount", pattern="^(amount|count)$"),
    db: Session = Depends(get_db),
) -> CategoryAnalyticsResponse:
    analytics = CategoryAnalyticsService(db).build(
        family_id=family_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        account_id=account_id,
        scope=scope,
        include_subcategories=include_subcategories,
        limit=limit,
        sort_by=sort_by,
    )
    return _category_response(analytics)


@router.get("/timeline", response_model=TimelineAnalyticsResponse)
def get_analytics_timeline(
    family_id: UUID = Query(...),
    occurred_from: datetime | None = Query(None),
    occurred_to: datetime | None = Query(None),
    account_id: UUID | None = Query(None),
    scope: str | None = Query(None),
    granularity: str = Query("day", pattern="^day$"),
    db: Session = Depends(get_db),
) -> TimelineAnalyticsResponse:
    analytics = TimelineAnalyticsService(db).build(
        family_id=family_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        account_id=account_id,
        scope=scope,
        granularity=granularity,
    )
    return _timeline_response(analytics)


@router.get("/dashboard", response_model=AnalyticsDashboardResponse)
def get_analytics_dashboard(
    family_id: UUID = Query(...),
    occurred_from: datetime | None = Query(None),
    occurred_to: datetime | None = Query(None),
    account_id: UUID | None = Query(None),
    scope: str | None = Query(None),
    category_limit: int = Query(5, ge=1, le=20),
    merchant_limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> AnalyticsDashboardResponse:
    common_filters = {
        "family_id": family_id,
        "occurred_from": occurred_from,
        "occurred_to": occurred_to,
        "account_id": account_id,
        "scope": scope,
    }
    summary = AnalyticsSummaryService(db).build(**common_filters)
    timeline = TimelineAnalyticsService(db).build(**common_filters, granularity="day")
    top_categories = CategoryAnalyticsService(db).build(
        **common_filters,
        include_subcategories=False,
        limit=category_limit,
        sort_by="amount",
    )
    top_merchants = MerchantAnalyticsService(db).build(
        **common_filters,
        category_id=None,
        limit=merchant_limit,
        sort_by="amount",
    )
    return AnalyticsDashboardResponse(
        summary=_summary_response(summary),
        timeline=_timeline_response(timeline),
        top_categories=_category_response(top_categories),
        top_merchants=_merchant_response(top_merchants),
    )


def _summary_response(summary) -> AnalyticsSummaryResponse:
    return AnalyticsSummaryResponse(
        income=summary.income,
        expenses=summary.expenses,
        savings=summary.savings,
        transfers=summary.transfers,
        net_cash_flow=summary.net_cash_flow,
        average_daily_expense=summary.average_daily_expense,
        transaction_count=summary.transaction_count,
        expense_count=summary.expense_count,
        income_count=summary.income_count,
        savings_count=summary.savings_count,
        transfer_count=summary.transfer_count,
        needs_review_count=summary.needs_review_count,
        uncategorized_count=summary.uncategorized_count,
        work_fop_count=summary.work_fop_count,
    )


def _merchant_response(analytics) -> MerchantAnalyticsResponse:
    return MerchantAnalyticsResponse(
        total_amount=analytics.total_amount,
        total_transactions=analytics.total_transactions,
        rows=[
            MerchantAnalyticsRowResponse(
                merchant_id=str(row.merchant_id),
                merchant_name=row.merchant_name,
                merchant_type=row.merchant_type,
                amount=row.amount,
                transaction_count=row.transaction_count,
                share_percent=row.share_percent,
            )
            for row in analytics.rows
        ],
    )


def _category_response(analytics) -> CategoryAnalyticsResponse:
    return CategoryAnalyticsResponse(
        total_amount=analytics.total_amount,
        total_transactions=analytics.total_transactions,
        rows=[
            CategoryAnalyticsRowResponse(
                category_id=str(row.category_id) if row.category_id else None,
                category_name=row.category_name,
                subcategory_id=str(row.subcategory_id) if row.subcategory_id else None,
                subcategory_name=row.subcategory_name,
                amount=row.amount,
                transaction_count=row.transaction_count,
                share_percent=row.share_percent,
            )
            for row in analytics.rows
        ],
    )


def _timeline_response(analytics) -> TimelineAnalyticsResponse:
    return TimelineAnalyticsResponse(
        granularity=analytics.granularity,
        rows=[
            TimelineBucketResponse(
                period=row.period,
                income=row.income,
                expenses=row.expenses,
                savings=row.savings,
                transfers=row.transfers,
                net_cash_flow=row.net_cash_flow,
                transaction_count=row.transaction_count,
                expense_count=row.expense_count,
                income_count=row.income_count,
                savings_count=row.savings_count,
                transfer_count=row.transfer_count,
            )
            for row in analytics.rows
        ],
    )
