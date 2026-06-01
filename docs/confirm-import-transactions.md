# Confirm Import And Create Transactions

Этот слой применяет draft preview и создает финальные `transactions`.

## Аналогия с Unity

Preview import похож на окно import settings: данные уже распознаны, но еще не попали в основную игровую модель.

Confirm import - это кнопка `Apply`. После нее временный preview становится постоянными данными, на которых будут работать отчеты, графики и рекомендации.

## Что делает `ConfirmImportService`

Модуль: `backend/app/services/confirm_import.py`.

Сервис:

- находит `ImportBatch` по `family_id` и `import_batch_id`;
- проверяет, что import все еще в статусе `draft`;
- проверяет, что выбранный `account_id` принадлежит этой семье;
- блокирует подтверждение, если в preview есть строки со статусом `error`;
- пропускает строки `excluded` и `duplicate_candidate`;
- создает `Transaction` для остальных строк;
- создает `Merchant`, если такого merchant еще нет;
- создает `PaymentInstrument`, если такой карты/инструмента еще нет;
- переводит `ImportBatch` в статус `confirmed`.

## Почему нужен `account_id`

`Transaction` обязан ссылаться на источник денег. В MVP мы передаем `account_id` при подтверждении импорта.

Если в выписке несколько карт одного счета, они сохраняются как `PaymentInstrument` внутри выбранного account. Это соответствует нашему правилу: физическая и виртуальная карта могут быть разными инструментами, но деньги лежат в одном источнике.

## API

```text
POST /api/v1/imports/{import_batch_id}/confirm
```

Query parameters для dev/MVP:

- `family_id`;
- `account_id`;
- `owner_user_id`, опционально.

Ответ:

- `import_batch_id`;
- `status`;
- `created_transactions`.

## Что дальше

Следующий шаг - endpoint списка транзакций:

- `GET /api/v1/transactions`;
- фильтры по датам, категориям, merchant, flow type и scope;
- этот endpoint станет первой основой для dashboard и графиков.
