# Analytics Summary API

Первый analytics endpoint дает верхние KPI по финальным `transactions`.

## Аналогия с Unity

`GET /transactions` похож на Hierarchy view: показывает список объектов.

`GET /analytics/summary` похож на Stats/Profiler panel: он не показывает каждую операцию, а собирает ключевые показатели за период.

## Endpoint

```text
GET /api/v1/analytics/summary
```

Query parameters:

- `family_id`, обязательный;
- `occurred_from`;
- `occurred_to`;
- `account_id`;
- `scope`.

## Что считается

Summary разделяет:

- `income` - входящие операции;
- `expenses` - обычные расходы;
- `savings` - накопления, например `Скарбничка`;
- `transfers` - переводы, кроме накоплений;
- `net_cash_flow` - доходы минус расходы и накопления;
- `average_daily_expense` - средний обычный расход в день;
- counts по операциям, review, uncategorized и work/FOP.

## Почему накопления отдельно от расходов

Для банковской выписки накопление выглядит как списание с карты. Но в семейной аналитике это не обычная трата, а перекладывание денег в накопления. Поэтому `transfer_to_savings` попадает в `savings`, а не в `expenses`.

## Что дальше

Следующие analytics endpoints:

- расходы по категориям;
- топ merchant по сумме;
- timeline расходов по дням;
- простые рекомендации на основе summary.
