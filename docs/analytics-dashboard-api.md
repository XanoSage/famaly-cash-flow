# Analytics Dashboard API

Этот endpoint собирает несколько аналитических блоков в один ответ для будущего главного экрана.

## Аналогия с Unity

Отдельные endpoints похожи на отдельные системы:

- `summary` — общие счетчики состояния;
- `timeline` — динамика по дням, как Profiler timeline;
- `by-category` — группировка расходов по типам событий;
- `by-merchant` — группировка расходов по местам покупок.

`dashboard` похож на HUD/controller: он не пересчитывает все с нуля, а собирает готовые данные из систем и отдает UI один пакет.

## Endpoint

```text
GET /api/v1/analytics/dashboard
```

Query parameters:

- `family_id`, обязательный;
- `occurred_from`;
- `occurred_to`;
- `account_id`;
- `scope`;
- `category_limit`, по умолчанию `5`, максимум `20`;
- `merchant_limit`, по умолчанию `5`, максимум `20`.

## Ответ

Ответ содержит:

- `summary` — ключевые итоги за период;
- `timeline` — дневная динамика;
- `top_categories` — топ категорий расходов;
- `top_merchants` — топ магазинов/получателей расходов.

Пример структуры:

```json
{
  "summary": {
    "income": "1000.00",
    "expenses": "300.00",
    "savings": "50.00",
    "transfers": "200.00",
    "net_cash_flow": "650.00"
  },
  "timeline": {
    "granularity": "day",
    "rows": []
  },
  "top_categories": {
    "total_amount": "300.00",
    "total_transactions": 2,
    "rows": []
  },
  "top_merchants": {
    "total_amount": "300.00",
    "total_transactions": 2,
    "rows": []
  }
}
```

## Зачем нужен

Frontend сможет загрузить стартовый dashboard одним запросом. Это проще и быстрее для MVP: экран получает все основные виджеты сразу, а отдельные endpoints остаются полезными для drill-down экранов.
