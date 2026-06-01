# Analytics Timeline API

Этот endpoint показывает движение денег во времени. Для MVP поддерживается группировка по дням: один день — один bucket.

## Аналогия с Unity

`summary` похож на общий счетчик в конце уровня: сколько заработали, сколько потратили, сколько отложили.

`timeline` похож на Unity Profiler: он показывает те же процессы по кадрам. Только вместо кадров у нас дни, а вместо FPS/draw calls — доходы, расходы, накопления и переводы.

## Endpoint

```text
GET /api/v1/analytics/timeline
```

Query parameters:

- `family_id`, обязательный;
- `occurred_from`;
- `occurred_to`;
- `account_id`;
- `scope`;
- `granularity`, пока только `day`.

## Что считается

Каждая операция попадает в день по `occurred_at.date()`.

Внутри дня суммы разделяются так:

- `income` — положительные операции с `direction = income`;
- `expenses` — обычные расходы, без переводов и накоплений;
- `savings` — операции `transfer_to_savings`;
- `transfers` — остальные переводы: себе, жене, человеку;
- `net_cash_flow` — `income - expenses - savings`.

Удаленные операции не попадают в расчет.

## Ответ

Ответ содержит:

- `granularity`;
- `rows` — отсортированные по дате дневные buckets.

Каждый bucket содержит дату, суммы по потокам денег и счетчики операций:

```json
{
  "period": "2026-05-01",
  "income": "1000.00",
  "expenses": "150.00",
  "savings": "50.00",
  "transfers": "0.00",
  "net_cash_flow": "800.00",
  "transaction_count": 3,
  "expense_count": 1,
  "income_count": 1,
  "savings_count": 1,
  "transfer_count": 0
}
```

## Что дальше

На этом endpoint можно строить первый line chart: расходы/доходы/накопления по дням. Позже сюда можно добавить `week` и `month`, чтобы UI переключал масштаб графика без пересчета на клиенте.
