# API Design

Документ описывает черновой API. Точные пути и схемы будут уточняться при реализации.

Все endpoint'ы находятся под префиксом:

```text
/api/v1
```

Подробные API-решения описаны в [API Contract Decisions](api-contract-decisions.md).

## Auth

- `POST /auth/login` - логин по email/password.
- `POST /auth/refresh` - обновление access token.
- `POST /auth/logout` - выход.
- `GET /auth/me` - текущий пользователь.

## Imports

- `POST /imports/xlsx/preview` - загрузить XLSX и получить preview.
- `POST /imports/xlsx/confirm` - подтвердить импорт выбранных операций.
- `GET /imports` - список импортов.
- `GET /imports/{id}` - детали импорта.
- `GET /imports/{id}/preview-rows` - строки draft preview с фильтрами.
- `PATCH /imports/{id}/preview-rows/{row_id}` - исправить одну preview-строку.
- `POST /imports/{id}/bulk-actions` - массовое действие по preview-строкам.
- `DELETE /imports/{id}` - удалить draft import.

Preview должен возвращать:

- распознанные операции;
- предполагаемую категорию;
- предполагаемого продавца;
- признак возможного дубля;
- ошибки разбора.

Confirm должен возвращать final summary:

- imported count;
- excluded count;
- duplicate count;
- error count;
- uncategorized count;
- work/FOP count;
- savings count.

## Transactions

- `GET /transactions` - список операций с фильтрами.
- `GET /transactions/{id}` - одна операция.
- `POST /transactions` - ручное создание операции.
- `PATCH /transactions/{id}` - редактирование операции.
- `DELETE /transactions/{id}` - soft delete операции.

## Categories

- `GET /categories` - список категорий с подкатегориями.
- `POST /categories` - создать категорию.
- `POST /categories/{id}/subcategories` - создать подкатегорию.
- `PATCH /categories/{id}` - редактировать категорию.

## Merchants

- `GET /merchants` - список продавцов.
- `GET /merchants/{id}/stats` - статистика по продавцу.
- `PATCH /merchants/{id}` - редактировать продавца.

## Rules

- `GET /categorization-rules` - список правил.
- `POST /categorization-rules` - создать правило.
- `PATCH /categorization-rules/{id}` - обновить правило.
- `DELETE /categorization-rules/{id}` - отключить правило.

## Analytics

- `GET /analytics/summary`
- `GET /analytics/by-category`
- `GET /analytics/by-merchant`
- `GET /analytics/timeline`
- `GET /analytics/insights`
- `GET /analytics/savings`
- `GET /analytics/subscriptions`
- `GET /analytics/work-fop`

Общие query parameters:

- `from`
- `to`
- `scope`
- `account_id`

## Cash

- `GET /cash/summary` - приблизительный наличный баланс.
- `POST /cash/expenses` - добавить наличный расход.
- `POST /cash/transfers` - зафиксировать снятие наличных.

## Budgets

- `GET /budgets/current` - текущий месячный бюджет.
- `POST /budgets/draft-from-history` - создать черновик бюджета по первой выписке или истории.
- `PUT /budgets/{id}` - обновить общий бюджет.
- `POST /budgets/{id}/limits` - добавить лимит по категории.
- `PATCH /budget-limits/{id}` - обновить лимит.
- `DELETE /budget-limits/{id}` - удалить лимит.

## Notifications

- `GET /notifications` - список уведомлений.
- `PATCH /notifications/{id}/read` - отметить уведомление прочитанным.

## API Documentation Level

В Markdown фиксируем endpoint + request/response schemas. Примеры JSON добавляются только для сложных endpoint'ов. FastAPI дополнительно генерирует OpenAPI/Swagger.
