from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics.categories import CategoryAnalyticsService
from app.analytics.merchants import MerchantAnalyticsService
from app.analytics.summary import AnalyticsSummaryService
from app.db.session import get_db
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    CategoryAnalyticsResponse,
    CategoryAnalyticsRowResponse,
    MerchantAnalyticsResponse,
    MerchantAnalyticsRowResponse,
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
