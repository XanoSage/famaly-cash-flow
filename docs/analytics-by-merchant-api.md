# Analytics By Merchant API

Этот endpoint показывает, где семья тратит деньги чаще всего и на какие суммы.

## Аналогия с Unity

Это leaderboard по merchant. Как в игре можно посмотреть топ источников damage или самые частые события, здесь можно посмотреть топ магазинов и сервисов.

## Endpoint

```text
GET /api/v1/analytics/by-merchant
```

Query parameters:

- `family_id`, обязательный;
- `occurred_from`;
- `occurred_to`;
- `account_id`;
- `category_id`;
- `scope`;
- `limit`, по умолчанию `10`, максимум `100`;
- `sort_by`: `amount` или `count`.

## Что считается

В расчет попадают только обычные расходы с merchant.

Не попадают:

- накопления `transfer_to_savings`;
- переводы;
- удаленные операции;
- операции без merchant.

Ответ содержит:

- `total_amount`;
- `total_transactions`;
- `rows` с merchant id/name/type, суммой, количеством операций и долей в процентах.

## Почему накопления и переводы исключаются

Для рейтинга магазинов нужны именно места покупок. Переводы и `Скарбничка` технически могут выглядеть как списания, но это не магазины и не сервисы, поэтому они не должны попадать в merchant leaderboard.
