# Import Preview API

Этот слой открывает HTTP-точку входа для загрузки банковской XLSX-выписки.

## Аналогия с Unity

До этого у нас была внутренняя логика импорта: parser и service. API route - это как UI Button или debug console command, который вызывает уже готовую систему.

Важно: route не должен знать всю бизнес-логику. Его задача - принять файл, проверить базовые параметры, вызвать service и вернуть DTO. Это похоже на то, как `MonoBehaviour` на кнопке не должен содержать всю экономику игры, а должен дернуть отдельный gameplay service.

## Endpoint

```text
POST /api/v1/imports/preview
```

Query parameters для dev/MVP:

- `family_id`;
- `uploaded_by_user_id`;
- `preview_limit`, по умолчанию `50`, максимум `200`.

Form-data:

- `file`: `.xlsx`.

## Что делает endpoint

1. Проверяет расширение файла.
2. Временно сохраняет upload на диск.
3. Вызывает `ImportPreviewService`.
4. Удаляет временный файл.
5. Возвращает summary и первые preview rows.

## Почему `family_id` и `uploaded_by_user_id` пока в query

Это временный dev-вариант до авторизации. Позже `uploaded_by_user_id` будет браться из JWT/current user, а `family_id` - из текущего семейного контекста пользователя.

## Что возвращается

Ответ содержит:

- `summary`: общий результат draft import;
- `rows`: preview rows, ограниченные `preview_limit`.

## Следующий шаг

После этого можно делать:

- endpoint получения preview по `import_batch_id`;
- endpoint подтверждения импорта;
- создание финальных `transactions`.
