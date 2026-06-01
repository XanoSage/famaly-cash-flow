# Analytics By Category API

Этот endpoint показывает распределение обычных расходов по категориям.

## Аналогия с Unity

Merchant analytics отвечает на вопрос "какие объекты создали больше всего затрат".

Category analytics отвечает на вопрос "какие типы событий съели бюджет": еда, здоровье, дети, дом и так далее.

## Endpoint

```text
GET /api/v1/analytics/by-category
```

Query parameters:

- `family_id`, обязательный;
- `occurred_from`;
- `occurred_to`;
- `account_id`;
- `scope`;
- `include_subcategories`, по умолчанию `false`;
- `limit`, по умолчанию `20`, максимум `100`;
- `sort_by`: `amount` или `count`.

## Что считается

В расчет попадают обычные расходы.

Не попадают:

- накопления `transfer_to_savings`;
- переводы;
- удаленные операции.

Операции без категории попадают в synthetic-группу `Uncategorized`, чтобы UI мог показать блок "разобрать позже".

## Ответ

Ответ содержит:

- `total_amount`;
- `total_transactions`;
- `rows` с category/subcategory id/name, суммой, количеством операций и долей в процентах.

## Что дальше

На этом endpoint можно строить первый bar chart расходов по категориям и drill-down в подкатегории.
