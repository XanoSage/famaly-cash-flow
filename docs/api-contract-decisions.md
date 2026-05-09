# API Contract Decisions

Документ фиксирует базовые решения по API-контрактам.

## API Style

Используем:

- REST API;
- FastAPI OpenAPI/Swagger;
- Markdown schemas для ключевых контрактов.

## Route Prefix

Все endpoint'ы MVP находятся под:

```text
/api/v1
```

Вопрос про разницу вариантов `2` и `5` в опроснике: разницы не было, это дубль формулировки. Итоговое решение: versioned REST prefix `/api/v1/...`.

## Error Format

Единый формат ошибки:

```json
{
  "code": "transaction_not_found",
  "message": "Transaction not found",
  "message_key": "errors.transaction_not_found",
  "details": {}
}
```

`message` может быть техническим или fallback-текстом. UI по возможности использует `message_key` для локализации.

## Pagination

Для таблиц операций используется offset/limit.

Пример query:

```text
GET /api/v1/transactions?offset=0&limit=50
```

Cursor pagination можно добавить позже, если таблицы станут очень большими.

## Language Resolution

Язык API определяется так:

1. User preferences.
2. Fallback через `Accept-Language`.
3. Fallback language: `ru` или системное значение проекта.

## System Category Translations

Для системных категорий используются translation keys.

Пользовательские категории, комментарии и merchant names остаются как введены пользователем.

## Migrations

Используем Alembic:

- autogenerate;
- обязательный ручной review миграции перед применением.

## Audit Log

MVP audit log покрывает:

- import batches;
- изменения операций;
- изменения правил категоризации.

Логин/выход можно добавить позже, если понадобится.

## Secrets

В репозитории:

- `.env.example`;
- без реальных secrets.

Локально:

- `.env` вне Git.

Production:

- Secret Manager.

GitHub Actions:

- GitHub secrets для CI/CD-интеграций, где нужно.

