# Analytics Work/FOP API

Этот endpoint показывает рабочие/FOP операции отдельно от семейной аналитики.

## Аналогия с Unity

`scope = work_fop` похож на отдельный Layer. Семейный dashboard смотрит на семейный слой, а Work/FOP endpoint включает только рабочий слой. Так рабочие подписки, сервисы и доходы не смешиваются с семейными тратами.

## Endpoint

```text
GET /api/v1/analytics/work-fop
```

Query parameters:

- `family_id`, обязательный;
- `occurred_from`;
- `occurred_to`;
- `account_id`;
- `category_limit`, по умолчанию `5`, максимум `20`;
- `merchant_limit`, по умолчанию `5`, максимум `20`.

Параметра `scope` здесь нет намеренно: endpoint всегда использует `scope = work_fop`.

## Ответ

Ответ похож на dashboard, но только для рабочих операций:

- `summary` — доходы, расходы, net cash flow и счетчики;
- `timeline` — динамика по дням;
- `top_categories` — рабочие категории расходов;
- `top_merchants` — рабочие сервисы/получатели.

Пример:

```json
{
  "summary": {
    "income": "3000.00",
    "expenses": "700.00",
    "net_cash_flow": "2300.00"
  },
  "timeline": {
    "granularity": "day",
    "rows": []
  },
  "top_categories": {
    "total_amount": "700.00",
    "rows": []
  },
  "top_merchants": {
    "total_amount": "700.00",
    "rows": []
  }
}
```

## Для UI

Этот endpoint можно использовать для отдельной карточки на dashboard:

- сколько рабочих операций найдено;
- рабочие расходы за период;
- рабочие доходы за период;
- переход в drill-down список с фильтром Work/FOP.
