# Analytics Insights API

Этот endpoint возвращает простые фактические подсказки по данным за период.

## Аналогия с Unity

Insights похожи на scripted events. Система смотрит на состояние аналитики и создает короткое событие для UI:

- есть расходы без категории;
- денежный поток отрицательный;
- крупнейшая категория расходов;
- топ мест покупок;
- накопления и примерный годовой темп.

Это не AI-советник и не прогноз “из воздуха”. В MVP каждая подсказка основана на уже посчитанных числах.

## Endpoint

```text
GET /api/v1/analytics/insights
```

Query parameters:

- `family_id`, обязательный;
- `occurred_from`;
- `occurred_to`;
- `account_id`;
- `scope`;
- `limit`, по умолчанию `10`, максимум `20`.

## Ответ

Ответ содержит `rows`. Каждая строка:

- `code` — стабильный код для UI;
- `title` — короткий заголовок;
- `message` — текст подсказки;
- `severity` — `info`, `warning` или `positive`;
- `metric_name` — имя основной метрики;
- `metric_value` — значение основной метрики.

Пример:

```json
{
  "rows": [
    {
      "code": "top_category",
      "title": "Крупнейшая категория расходов",
      "message": "Food: 300.00 UAH (100.00% расходов).",
      "severity": "info",
      "metric_name": "top_category_amount",
      "metric_value": "300.00"
    }
  ]
}
```

## Правила MVP

Сейчас сервис может вернуть:

- `no_transactions`;
- `negative_cash_flow`;
- `needs_review`;
- `uncategorized_expenses`;
- `top_category`;
- `top_merchants`;
- `savings_progress`;
- `average_daily_expense`.

## Dashboard

`GET /api/v1/analytics/dashboard` тоже включает блок `insights`, чтобы главный экран мог загрузить подсказки одним запросом вместе с графиками и топами.
