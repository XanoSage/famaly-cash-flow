# Analytics Savings API

Этот endpoint показывает отдельный блок накоплений.

## Аналогия с Unity

Обычные расходы похожи на потраченные ресурсы в процессе уровня. Накопления похожи на отдельную валюту или XP: банк видит списание с карты, но для семьи это не покупка, а перенос денег в накопления.

Поэтому `transfer_to_savings` не смешивается с `expenses`, но сравнивается с ними рядом.

## Endpoint

```text
GET /api/v1/analytics/savings
```

Query parameters:

- `family_id`, обязательный;
- `occurred_from`;
- `occurred_to`;
- `account_id`;
- `scope`.

## Что считается

В расчет попадают:

- накопления с `flow_type = transfer_to_savings`;
- обычные расходы для сравнения.

Не попадают:

- переводы жене;
- переводы другим людям;
- переводы между своими счетами;
- удаленные операции.

## Ответ

Ответ содержит:

- `total_savings` — сколько отложено за период;
- `total_expenses` — обычные расходы за период;
- `savings_count` и `expense_count`;
- `savings_to_expenses_percent` — накопления как процент от обычных расходов;
- `average_daily_savings` — среднее накопление в день периода;
- `projected_yearly_savings` — примерный годовой темп;
- `period_days`;
- `rows` — дневная динамика накоплений и расходов.

Пример:

```json
{
  "total_savings": "150.00",
  "total_expenses": "300.00",
  "savings_count": 2,
  "expense_count": 2,
  "savings_to_expenses_percent": "50.00",
  "average_daily_savings": "75.00",
  "projected_yearly_savings": "27375.00",
  "period_days": 2,
  "rows": [
    {
      "period": "2026-05-01",
      "savings": "50.00",
      "expenses": "100.00",
      "savings_count": 1,
      "expense_count": 1
    }
  ]
}
```

## Для UI

Этот endpoint можно использовать для отдельной карточки накоплений на dashboard:

- KPI: накоплено за период;
- график: накопления по дням;
- сравнение: расходы vs накопления;
- прогноз: если темп сохранится, сколько примерно получится за год.
