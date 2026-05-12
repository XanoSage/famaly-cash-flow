from decimal import Decimal

from openpyxl import Workbook

from app.importers.bank_xlsx import parse_bank_xlsx


def test_parse_bank_xlsx_builds_preview_rows(tmp_path) -> None:
    path = tmp_path / "statement.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Виписки"
    worksheet.append(["Історія операцій за період 08.02.2026 - 08.05.2026"])
    worksheet.append(
        [
            "Дата",
            "Категорія",
            "Картка",
            "Опис операції",
            "Сума в валюті картки",
            "Валюта картки",
            "Сума в валюті транзакції",
            "Валюта транзакції",
            "Залишок на кінець періоду",
            "Валюта залишку",
        ]
    )
    worksheet.append(
        [
            "08.05.2026 15:25:00",
            "Супермаркети та продукти",
            "4627 **** **** 3421",
            "Сільпо",
            -118.02,
            "UAH",
            118.02,
            "UAH",
            6248.97,
            "UAH",
        ]
    )
    worksheet.append(
        [
            "08.05.2026 18:06:12",
            "Заощадження",
            "4627 **** **** 3421",
            "Скарбничка",
            -9.2,
            "UAH",
            9.2,
            "UAH",
            5266.99,
            "UAH",
        ]
    )
    workbook.save(path)

    result = parse_bank_xlsx(path)

    assert result.source_filename == "statement.xlsx"
    assert result.sheet_name == "Виписки"
    assert result.summary.total_rows == 2
    assert result.summary.auto_ready_count == 2
    assert result.summary.needs_review_count == 0
    assert result.summary.savings_count == 1
    assert result.summary.parser_version == "bank-xlsx-v1"

    supermarket_row = result.rows[0]
    assert supermarket_row.status == "auto_ready"
    assert supermarket_row.amount == Decimal("-118.02")
    assert supermarket_row.currency == "UAH"
    assert supermarket_row.merchant_name == "Сільпо"
    assert supermarket_row.proposed_flow_type == "purchase"
    assert supermarket_row.proposed_scope == "family"

    savings_row = result.rows[1]
    assert savings_row.status == "auto_ready"
    assert savings_row.proposed_flow_type == "transfer_to_savings"
    assert savings_row.normalized_payload["direction"] == "expense"


def test_parse_bank_xlsx_marks_person_transfers_for_review(tmp_path) -> None:
    path = tmp_path / "statement.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["Історія операцій за період 08.02.2026 - 08.05.2026"])
    worksheet.append(
        [
            "Дата",
            "Категорія",
            "Картка",
            "Опис операції",
            "Сума в валюті картки",
            "Валюта картки",
            "Сума в валюті транзакції",
            "Валюта транзакції",
            "Залишок на кінець періоду",
            "Валюта залишку",
        ]
    )
    worksheet.append(
        [
            "08.05.2026 10:00:00",
            "Перекази",
            "4627 **** **** 3421",
            "Переказ на картку",
            -700,
            "UAH",
            700,
            "UAH",
            1000,
            "UAH",
        ]
    )
    workbook.save(path)

    result = parse_bank_xlsx(path)

    assert result.summary.total_rows == 1
    assert result.summary.needs_review_count == 1
    assert result.rows[0].status == "needs_review"
    assert result.rows[0].proposed_flow_type == "person_transfer"
    assert result.rows[0].reason_codes == ["person_transfer"]
