from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.analytics.categories import CategoryAnalyticsService
from app.analytics.merchants import MerchantAnalyticsService
from app.analytics.summary import AnalyticsSummaryService
from app.analytics.timeline import TimelineAnalyticsService


@dataclass(frozen=True)
class AnalyticsInsight:
    code: str
    title: str
    message: str
    severity: str
    metric_name: str | None
    metric_value: Decimal | None


@dataclass(frozen=True)
class AnalyticsInsights:
    rows: list[AnalyticsInsight]


class AnalyticsInsightsService:
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
        limit: int = 10,
    ) -> AnalyticsInsights:
        common_filters = {
            "family_id": family_id,
            "occurred_from": occurred_from,
            "occurred_to": occurred_to,
            "account_id": account_id,
            "scope": scope,
        }
        summary = AnalyticsSummaryService(self.db).build(**common_filters)
        categories = CategoryAnalyticsService(self.db).build(**common_filters, limit=3)
        merchants = MerchantAnalyticsService(self.db).build(**common_filters, category_id=None, limit=3)
        timeline = TimelineAnalyticsService(self.db).build(**common_filters)

        insights: list[AnalyticsInsight] = []
        if summary.transaction_count == 0:
            insights.append(
                AnalyticsInsight(
                    code="no_transactions",
                    title="Нет данных за период",
                    message="За выбранный период нет операций. Загрузите выписку или добавьте расход вручную.",
                    severity="info",
                    metric_name="transaction_count",
                    metric_value=Decimal("0.00"),
                )
            )
            return AnalyticsInsights(rows=insights[:limit])

        if summary.net_cash_flow < 0:
            insights.append(
                AnalyticsInsight(
                    code="negative_cash_flow",
                    title="Расходы выше доходов",
                    message=(
                        "За период денежный поток отрицательный: "
                        f"{_money(summary.net_cash_flow)} UAH."
                    ),
                    severity="warning",
                    metric_name="net_cash_flow",
                    metric_value=summary.net_cash_flow,
                )
            )

        if summary.needs_review_count > 0:
            insights.append(
                AnalyticsInsight(
                    code="needs_review",
                    title="Есть операции на проверку",
                    message=(
                        f"{summary.needs_review_count} операций требуют проверки перед точной аналитикой."
                    ),
                    severity="warning",
                    metric_name="needs_review_count",
                    metric_value=Decimal(summary.needs_review_count),
                )
            )

        if summary.uncategorized_count > 0:
            insights.append(
                AnalyticsInsight(
                    code="uncategorized_expenses",
                    title="Есть расходы без категории",
                    message=f"{summary.uncategorized_count} расходов пока без категории.",
                    severity="info",
                    metric_name="uncategorized_count",
                    metric_value=Decimal(summary.uncategorized_count),
                )
            )

        if categories.rows:
            top_category = categories.rows[0]
            insights.append(
                AnalyticsInsight(
                    code="top_category",
                    title="Крупнейшая категория расходов",
                    message=(
                        f"{top_category.category_name}: {_money(top_category.amount)} UAH "
                        f"({top_category.share_percent}% расходов)."
                    ),
                    severity="info",
                    metric_name="top_category_amount",
                    metric_value=top_category.amount,
                )
            )

        if merchants.rows:
            names = ", ".join(row.merchant_name for row in merchants.rows)
            insights.append(
                AnalyticsInsight(
                    code="top_merchants",
                    title="Топ мест покупок",
                    message=f"Больше всего расходов за период: {names}.",
                    severity="info",
                    metric_name="top_merchants_total",
                    metric_value=merchants.total_amount,
                )
            )

        if summary.savings > 0:
            insights.append(
                AnalyticsInsight(
                    code="savings_progress",
                    title="Накопления работают",
                    message=_savings_message(summary.savings, _period_days(timeline.rows)),
                    severity="positive",
                    metric_name="savings",
                    metric_value=summary.savings,
                )
            )

        if summary.average_daily_expense > 0:
            insights.append(
                AnalyticsInsight(
                    code="average_daily_expense",
                    title="Средний расход в день",
                    message=f"Средний расход за активный день: {_money(summary.average_daily_expense)} UAH.",
                    severity="info",
                    metric_name="average_daily_expense",
                    metric_value=summary.average_daily_expense,
                )
            )

        return AnalyticsInsights(rows=insights[:limit])


def _period_days(rows) -> int:
    if not rows:
        return 0
    return max((rows[-1].period - rows[0].period).days + 1, 1)


def _savings_message(savings: Decimal, period_days: int) -> str:
    if period_days <= 0:
        return f"За период отложено {_money(savings)} UAH."
    yearly_projection = ((savings / Decimal(period_days)) * Decimal(365)).quantize(Decimal("0.01"))
    return (
        f"За период отложено {_money(savings)} UAH. "
        f"Если темп сохранится, за год получится около {_money(yearly_projection)} UAH."
    )


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"
