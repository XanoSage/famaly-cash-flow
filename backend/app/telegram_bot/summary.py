from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.analytics.summary import AnalyticsSummary, AnalyticsSummaryService


SUMMARY_NOT_CONFIGURED_TEXT = (
    "Сводка пока не настроена.\n\n"
    "Добавь TELEGRAM_DEFAULT_FAMILY_ID в backend .env, чтобы команда /summary знала, "
    "для какой семьи считать данные."
)
SUMMARY_INVALID_FAMILY_ID_TEXT = (
    "TELEGRAM_DEFAULT_FAMILY_ID настроен неверно.\n\n"
    "Укажи UUID семьи из demo seed или из базы."
)


def build_summary_text(db: Session, family_id_value: str | None) -> str:
    if family_id_value is None or not family_id_value.strip():
        return SUMMARY_NOT_CONFIGURED_TEXT

    family_id = _parse_family_id(family_id_value)
    if family_id is None:
        return SUMMARY_INVALID_FAMILY_ID_TEXT

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


def _parse_family_id(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _format_money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", " ")
