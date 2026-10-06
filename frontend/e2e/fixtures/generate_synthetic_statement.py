from pathlib import Path

from openpyxl import Workbook


OUTPUT = Path(__file__).with_name("synthetic-e2e-statement.xlsx")
CARD = "4000 **** **** 4242"
HEADERS = [
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


def main() -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Виписки"
    worksheet.append(["Synthetic E2E statement for 01.10.2026 - 03.10.2026"])
    worksheet.append(HEADERS)

    rows = [
        ("01.10.2026 10:00:00", "Супермаркети та продукти", "E2E Market", -1200.00),
        ("01.10.2026 10:00:00", "Супермаркети та продукти", "E2E Market", -1200.00),
        ("02.10.2026 11:30:00", "Кафе", "E2E Cafe", -90.00),
        ("02.10.2026 14:00:00", "Зарплата", "E2E Payroll", 2000.00),
        ("03.10.2026 09:15:00", "Перекази", "E2E Person Transfer", -400.00),
        ("03.10.2026 10:20:00", "Зняття готівки", "E2E ATM Withdrawal", -500.00),
        ("03.10.2026 12:45:00", "Інше", "E2E New Merchant", -60.00),
    ]
    for index, (occurred_at, category, description, amount) in enumerate(rows, start=1):
        worksheet.append(
            [
                occurred_at,
                category,
                CARD,
                description,
                amount,
                "UAH",
                abs(amount),
                "UAH",
                10_000.00 - index * 100,
                "UAH",
            ]
        )
    workbook.save(OUTPUT)
    workbook.close()


if __name__ == "__main__":
    main()
