# Transactions API

Этот слой открывает список финальных операций после подтверждения импорта.

## Аналогия с Unity

Если import preview - это окно настроек импорта, то `transactions` - это уже объекты, примененные в проект.

`GET /transactions` похож на Project/Hierarchy view: он не меняет данные, а дает frontend возможность увидеть, отфильтровать и пролистать реальные операции.

## Endpoint

```text
GET /api/v1/transactions
```

Query parameters для dev/MVP:

- `family_id`, обязательный;
- `offset`, по умолчанию `0`;
- `limit`, по умолчанию `50`, максимум `200`;
- `occurred_from`;
- `occurred_to`;
- `account_id`;
- `merchant_id`;
- `category_id`;
- `flow_type`;
- `scope`;
- `needs_review`;
- `include_deleted`, по умолчанию `false`.

## Ответ

Ответ содержит:

- `total`: сколько операций подходит под фильтры;
- `offset`;
- `limit`;
- `rows`: страница операций.

Каждая строка содержит основные поля транзакции, включая:

- дату;
- сумму;
- валюту;
- direction;
- flow type;
- scope;
- description;
- merchant id/name;
- category/subcategory ids;
- признак `needs_review`.

## Почему это следующий шаг

Этот endpoint станет основой для:

- таблицы операций во frontend;
- dashboard;
- графиков по категориям;
- статистики по merchant;
- будущего редактирования операций.
