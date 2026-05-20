# Import Preview API

Этот слой открывает HTTP-точки входа для загрузки банковской XLSX-выписки и повторного открытия сохраненного draft preview.

## Аналогия с Unity

До этого у нас была внутренняя логика импорта: parser и service. API route - это как UI Button или debug console command, который вызывает уже готовую систему.

Важно: route не должен знать всю бизнес-логику. Его задача - принять запрос, проверить базовые параметры, вызвать service или достать данные из БД и вернуть DTO. Это похоже на то, как `MonoBehaviour` на кнопке не должен содержать всю экономику игры, а должен дернуть отдельный gameplay service.

## Upload Endpoint

```text
POST /api/v1/imports/preview
```

Query parameters для dev/MVP:

- `family_id`;
- `uploaded_by_user_id`;
- `preview_limit`, по умолчанию `50`, максимум `200`.

Form-data:

- `file`: `.xlsx`.

Что делает endpoint:

1. Проверяет расширение файла.
2. Временно сохраняет upload на диск.
3. Вызывает `ImportPreviewService`.
4. Удаляет временный файл.
5. Возвращает summary и первые preview rows.

## Reopen Endpoint

```text
GET /api/v1/imports/{import_batch_id}/preview
```

Query parameters для dev/MVP:

- `family_id`;
- `offset`, по умолчанию `0`;
- `limit`, по умолчанию `50`, максимум `200`;
- `row_status`, опционально: например `auto_ready`, `needs_review`, `error`.

Что делает endpoint:

1. Находит draft import по `import_batch_id` и `family_id`.
2. Возвращает summary.
3. Возвращает страницу preview rows.
4. Если указан `row_status`, возвращает только строки с этим статусом.

Это нужно frontend, чтобы можно было открыть уже созданный preview повторно: например после refresh страницы, перехода между экранами или выбора фильтра "требуют проверки".

## Почему `family_id` и `uploaded_by_user_id` пока в query

Это временный dev-вариант до авторизации. Позже `uploaded_by_user_id` будет браться из JWT/current user, а `family_id` - из текущего семейного контекста пользователя.

## Что возвращается

Ответ содержит:

- `summary`: общий результат draft import;
- `rows`: preview rows, ограниченные `preview_limit` или `limit`.

`summary` также содержит `offset` и `limit`, чтобы UI понимал, какую страницу строк он получил.

## Следующий шаг

После этого можно делать:

- endpoint подтверждения импорта;
- создание финальных `transactions`;
- ручное редактирование preview rows перед подтверждением.
