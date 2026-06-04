from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.analytics.categories import CategoryAnalytics
from app.analytics.categories import CategoryAnalyticsService
from app.analytics.merchants import MerchantAnalytics
from app.analytics.merchants import MerchantAnalyticsService
from app.analytics.summary import AnalyticsSummary
from app.analytics.summary import AnalyticsSummaryService
from app.analytics.timeline import TimelineAnalytics
from app.analytics.timeline import TimelineAnalyticsService

WORK_FOP_SCOPE = "work_fop"


@dataclass(frozen=True)
class WorkFopAnalytics:
    summary: AnalyticsSummary
    timeline: TimelineAnalytics
    top_categories: CategoryAnalytics
    top_merchants: MerchantAnalytics


class WorkFopAnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build(
        self,
        *,
        family_id: UUID,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        account_id: UUID | None = None,
        category_limit: int = 5,
        merchant_limit: int = 5,
    ) -> WorkFopAnalytics:
        common_filters = {
            "family_id": family_id,
            "occurred_from": occurred_from,
            "occurred_to": occurred_to,
            "account_id": account_id,
            "scope": WORK_FOP_SCOPE,
        }
        return WorkFopAnalytics(
            summary=AnalyticsSummaryService(self.db).build(**common_filters),
            timeline=TimelineAnalyticsService(self.db).build(**common_filters, granularity="day"),
            top_categories=CategoryAnalyticsService(self.db).build(
                **common_filters,
                include_subcategories=False,
                limit=category_limit,
                sort_by="amount",
            ),
            top_merchants=MerchantAnalyticsService(self.db).build(
                **common_filters,
                category_id=None,
                limit=merchant_limit,
                sort_by="amount",
            ),
        )
