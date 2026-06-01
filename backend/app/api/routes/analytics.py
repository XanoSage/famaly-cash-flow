from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics.summary import AnalyticsSummaryService
from app.db.session import get_db
from app.schemas.analytics import AnalyticsSummaryResponse

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
