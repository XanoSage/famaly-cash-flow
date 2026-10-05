# Import Preview Flow

Документ описывает пользовательский flow после загрузки XLSX-выписки.

## Цель

Preview нужен, чтобы пользователь мог безопасно проверить операции перед импортом:

- увидеть общую картину файла;
- разобрать сомнительные операции;
- исключить дубли;
- сохранить правила на будущее;
- подтвердить импорт без потери контроля.

## Экран после загрузки

После загрузки XLSX пользователь видит:

1. Summary сверху.
2. Таблицу операций снизу.
3. По умолчанию включенный фильтр `Требуют проверки`.

## Summary

Summary показывает:

- период выписки;
- всего операций;
- расходы;
- доходы;
- накопления;
- переводы;
- сколько распознано автоматически;
- сколько требует проверки;
- сколько возможных дублей;
- сколько будет импортировано;
- сколько исключено.

## Preview Statuses

Операция в preview может иметь один из статусов:

| Status | Meaning |
| --- | --- |
| `auto_ready` | Готова к импорту автоматически. |
| `needs_review` | Требует проверки пользователем. |
| `duplicate_candidate` | Возможный дубль. |
| `excluded` | Исключена из импорта. |
| `error` | Ошибка разбора строки. |

## Reason Codes

Операция может иметь одну или несколько причин статуса:

- `new_merchant`;
- `large_amount`;
- `large_supermarket`;
- `person_transfer`;
- `wife_transfer`;
- `requisites_payment`;
- `low_confidence`;
- `work_fop_candidate`;
- `duplicate`;
- `parse_error`;
- `uncategorized`;
- `rule_conflict`.

## Duplicate Handling

Возможные дубли:

- исключаются из импорта по умолчанию;
- показывают похожую уже импортированную операцию;
- могут быть вручную включены в импорт;
- доступны через отдельный фильтр `Дубли`.

Похожая операция должна показывать:

- дату;
- сумму;
- описание;
- merchant;
- категорию;
- import batch, если доступен.

## Needs Review Completion

Операция `needs_review` становится готовой к импорту, когда заполнены обязательные поля. Пользователь также может осознанно выбрать `Без категории`.

Обязательные поля по типу операции:

| Operation Type | Required Decision |
| --- | --- |
| Обычный расход | Категория/подкатегория или `Без категории`. |
| Перевод физлицу | Flow type + категория или оставить как перевод. |
| Перевод жене | Компенсация семейной траты, личные расходы жены или просто перевод жене. |
| Платеж по реквизитам | Получатель + категория/подкатегория. |
| Рабочая/FOP операция | Scope `work_fop` + рабочая категория или исключение из семейной аналитики. |
| Входящая операция | Income type: доход, возврат, свой перевод, долг или другое. |

## Table Filters

Preview table должна поддерживать фильтры:

- все операции;
- требуют проверки;
- дубли;
- переводы;
- крупные операции;
- новые продавцы;
- ошибки;
- без категории;
- рабочие/FOP кандидаты;
- merchant;
- bank category;
- proposed category;
- payment instrument.

## Bulk Actions

Пользователь может:

- выбрать несколько операций и назначить категорию;
- назначить категорию всем операциям одного merchant;
- применить исправление ко всем похожим операциям текущего импорта;
- исключить выбранные операции;
- включить выбранные duplicate candidates;
- сохранить правило на будущее.

Перед массовым действием UI показывает, сколько операций изменится.

## Rule Creation

Правило предлагается, когда merchant или получатель повторяется.

UI показывает чекбокс `Создать правило на будущее` рядом с массовым действием или исправлением.

Правило не создается автоматически без подтверждения.

## Rule Content

Правило может включать:

- merchant -> category/subcategory;
- merchant -> flow_type;
- merchant/recipient -> scope;
- bank category + keyword -> category;
- priority;
- enabled/disabled flag.

## Rule Conflicts

Конфликт правил решается так:

- у правил есть `priority`;
- merchant rule по умолчанию сильнее bank category;
- если правила дают разные важные результаты или уверенность низкая, операция идет на проверку;
- preview показывает reason `rule_conflict`.

## Final Summary

Перед финальным импортом пользователь видит summary:

- сколько операций будет импортировано;
- сколько исключено;
- сколько дублей исключено;
- сколько осталось без категории;
- сколько рабочих/FOP;
- сколько накоплений;
- сколько переводов;
- какие ошибки остались.

UI показывает предупреждение, если есть операции без категории или `error`.

## Import Blocking Rules

Импорт нельзя завершить, пока строки со статусом `error` не исправлены или явно не исключены.

Импорт можно завершить с операциями без категории, если пользователь видит предупреждение. Такие операции попадают в `Разобрать позже`.

Ограничение по сумме операций без категории добавляется позже, если понадобится.

## ImportBatch Saved Data

После подтверждения сохраняются:

- имя файла;
- дата загрузки;
- пользователь;
- период выписки;
- всего строк;
- сколько импортировано;
- сколько исключено;
- сколько дублей;
- сколько ошибок;
- сколько без категории;
- сколько рабочих/FOP;
- сколько накоплений;
- список ошибок и исключенных строк без хранения полного XLSX;
- версия парсера;
- версия маппинга правил.

## Draft Import

Preview сохраняется как draft import в базе.

Правила:

- пользователь может вернуться к проверке позже;
- draft очищается автоматически через 7 дней;
- draft можно удалить вручную;
- исходный XLSX как файл не хранится.

## Implemented backend review contract

The backend stores review decisions on the preview row and exposes these authenticated,
Family-scoped routes (the Family always comes from the current User):

- `POST /api/v1/imports/preview` parses XLSX, applies system/family rules, checks existing
  same-Family Transactions and repeated rows in the file, and returns a paginated preview.
- `GET /api/v1/imports/{batch_id}/preview` retrieves the saved preview. It supports pagination and
  filters `row_status`, `reason_code`, `merchant`, `bank_category`, `proposed_category_id`, and
  `uncategorized_only`. `total_rows` is the full batch size, `matching_rows_count` is the filtered
  row count, and status summary counters describe the full batch.
- `PATCH /api/v1/imports/{batch_id}/preview/{row_id}` edits one row. Accepted fields are
  `proposed_category_id`, `proposed_subcategory_id`, `proposed_flow_type`, `proposed_scope`,
  `merchant_name`, `excluded`, `include_duplicate`, and `accept_uncategorized`. `apply_to_merchant`
  applies those values to matching normalized merchant names in this draft only. `save_rule` opts
  into creating/updating an exact merchant rule for future imports.
- `POST /api/v1/imports/{batch_id}/bulk-actions` accepts `row_ids`, `action`, optional proposed
  fields, and optional `apply_to_merchant` / `save_rule`. Actions are `assign_category`, `set_scope`,
  `set_flow_type`, `exclude`, `include_duplicate`, `mark_uncategorized`, and `apply_correction`.
  Returned counts distinguish requested IDs, rows matched in the draft, and rows changed.
- `POST /api/v1/imports/{batch_id}/confirm?account_id=...` creates Transactions from the reviewed
  state. It rejects batches outside the caller's Family, non-drafts, and unresolved error rows. An
  excluded parse-error row no longer blocks confirmation. Excluded rows and unresolved duplicate
  candidates are skipped; a duplicate candidate is imported only after explicit inclusion. A
  second confirmation is rejected because the batch is already confirmed.

Category IDs must refer to a system-global or caller-Family Category. A subcategory must belong to
the selected category. Foreign draft IDs and row IDs from a different draft are rejected. Parse-error
date/amount/source values cannot yet be edited; those rows can be excluded. The response returns
category/subcategory IDs and names, proposed flow/scope, review markers, duplicate row/transaction
metadata, and an existing-transaction summary only when that transaction belongs to the caller's
Family.

An explicit uncategorized choice sets `reviewed_uncategorized = true`; a null category by itself
still means the row has not been consciously accepted without a category. Duplicate inclusion is
stored separately from the factual `duplicate` reason. Review edits recompute statuses and counters
from the stored rows rather than trusting parser summary values.

## Re-Uploading Same File

Если пользователь загружает тот же XLSX второй раз, сервис:

- предупреждает по имени файла и периоду;
- дополнительно определяет совпадение по операциям;
- показывает сообщение `Похоже, этот период уже импортирован`;
- разрешает продолжить;
- дубли исключаются по умолчанию.

