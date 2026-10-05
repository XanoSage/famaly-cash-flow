from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.analytics.summary import AnalyticsSummary, AnalyticsSummaryService


def build_summary_text(db: Session, family_id: UUID) -> str:
    summary = AnalyticsSummaryService(db).build(family_id=family_id)
    return format_summary_text(summary)


def format_summary_text(summary: AnalyticsSummary) -> str:
    return (
        "Сводка Family Cash Flow\n\n"
        f"Доходы: {_format_money(summary.income)} UAH\n"
        f"Расходы: {_format_money(summary.expenses)} UAH\n"
        f"Накопления: {_format_money(summary.savings)} UAH\n"
        f"Cash flow: {_format_money(summary.net_cash_flow)} UAH\n\n"
        f"Операций: {summary.transaction_count}\n"
        f"На проверку: {summary.needs_review_count}\n"
        f"Без категории: {summary.uncategorized_count}"
    )


def _format_money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", " ")
