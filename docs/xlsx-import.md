# XLSX Import

## Цель

Импорт должен превращать банковскую XLSX-выписку в нормализованный список операций, который пользователь проверяет перед сохранением.

## Поток импорта

1. Пользователь загружает XLSX.
2. Backend парсит файл.
3. Сервис нормализует даты, суммы, описания и продавцов.
4. Сервис проверяет возможные дубли.
5. Сервис предлагает категории и подкатегории.
6. Frontend показывает preview.
7. Пользователь исправляет спорные операции.
8. Пользователь подтверждает импорт.
9. Операции сохраняются в базе.
10. Исходный XLSX удаляется, метаданные импорта остаются.

Подробный пользовательский flow preview описан в [Import Preview Flow](import-preview-flow.md).

## Дубли

Приоритет проверки:

1. `bank_transaction_id`, если он есть в XLSX.
2. Иначе комбинация:
   - дата;
   - сумма;
   - описание;
   - аккаунт.

В preview возможные дубли показываются и по умолчанию не импортируются.

The implemented conservative fallback compares an active Transaction from the same Family using
the exact bank timestamp, signed amount, currency, and normalized non-empty description. If both
records have a payment-instrument label, the labels must also match. Date/amount similarity alone
does not qualify. Imported bank timestamps currently remain naive local wall times; matching does
not infer a timezone. A later bank-provided transaction ID can be added as a stronger key.

Within one uploaded statement, later rows with exactly equal timestamp, signed amount, currency,
normalized description/merchant, and payment-instrument label are marked as duplicates of the first
row. The API returns the first row number; it does not create preview-row foreign-key cycles. A
re-upload after confirmation is matched against the already-created same-Family Transactions.

## Категоризация на preview

Сервис предлагает категорию на основании:

- предустановленных ключевых слов;
- правила продавец -> категория;
- пользовательских правил;
- будущей AI-классификации.

The parser only extracts facts and its initial flow/scope hints. The import-review service applies
persisted family/system categorization rules and computes final status/reason codes before the draft
is returned. No Merchant is persisted until confirmation.

### Current review API behavior

The XLSX parser continues to keep bank timestamps naive because the source file has no timezone
offset. Confirmed transactions use the parsed wall time. Setting a consistent timezone for imported
bank operations is still a separate product decision; Telegram manual transactions are UTC-aware.

## Что нужно выяснить после получения реальной выписки

- Как отличать несколько карт внутри одного банковского источника.
- Какие банковские категории считать расходом, переводом, доходом, накоплением или технической операцией.
- Как нормализовать продавцов из `Опис операції`.
- Как обрабатывать операции `Скарбничка` и другие накопления.
- Как показывать транзакции, где счет в UAH, а валюта транзакции USD/EUR.

## Реальная выписка: первичные выводы

Подробности зафиксированы в [Bank XLSX Analysis](bank-xlsx-analysis.md).

Ключевые выводы:

- лист один: `Виписки`;
- заголовки находятся во второй строке;
- данные начинаются с третьей строки;
- явного ID операции нет;
- направление операции определяется знаком поля `Сума в валюті картки`;
- продавца можно первично брать из поля `Опис операції`;
- банковскую категорию стоит сохранять как `bank_category_raw`;
- дубли для MVP нужно искать по fallback-ключу: дата, сумма, описание, карта;
- карта в выписке уже маскирована;
- счет в UAH, но валюта транзакции может быть UAH, USD или EUR.
- физическая и виртуальная карта одного счета должны связываться с одним account, но сохраняться как payment instruments;
- `Скарбничка` и похожие операции классифицируются как накопления, а не как обычные расходы;
- переводы физлицам и платежи по реквизитам требуют review в первый раз, затем могут обрабатываться правилами.

## Review Rules

Операция должна попасть в список "требует проверки", если выполняется хотя бы одно условие:

- перевод физлицу или "на картку";
- платеж по реквизитам без сохраненного правила получателя;
- сумма больше настраиваемого лимита крупной операции, по умолчанию 5000 UAH;
- новый продавец без правила;
- низкая уверенность категоризации;
- потенциально рабочая/FOP операция;
- возможный дубль.
- супермаркетный чек больше настраиваемого лимита, по умолчанию 2500 UAH.

## Preview UX Requirements

Preview импорта должен показывать:

- дату и время;
- signed amount in UAH;
- оригинальную сумму и валюту транзакции, если отличается от UAH;
- описание операции;
- продавца;
- банковскую категорию;
- предложенную категорию сервиса;
- payment instrument;
- статус: auto categorized, needs review, duplicate candidate, skipped.

После ручного исправления система предлагает:

- применить исправление к похожим операциям в текущем импорте;
- сохранить правило для будущих импортов;
- оставить исправление только для этой операции.

## Draft Imports

Preview сохраняется как draft import в базе. Это позволяет вернуться к проверке позже, если в выписке много строк.

Правила:

- draft import хранится до подтверждения или ручного удаления;
- неподтвержденные draft imports автоматически очищаются через 7 дней;
- исходный XLSX как файл не хранится;
- в базе хранится нормализованный preview и технические метаданные.
