# Data Model

Документ описывает предварительную модель данных. Она будет уточняться после анализа реальной XLSX-выписки.

## Family

Семейный профиль.

Поля:

- `id`
- `name`
- `created_at`

## User

Пользователь внутри семьи.

Поля:

- `id`
- `family_id`
- `email`
- `password_hash`
- `display_name`
- `created_at`

## Account

Источник денег: карта, наличный кошелек, позже другие счета.

Поля:

- `id`
- `family_id`
- `owner_user_id`
- `type`: `card`, `cash`
- `name`
- `currency`: `UAH`
- `is_active`

## PaymentInstrument

Физический способ доступа к account: физическая карта, виртуальная карта, token.

Поля:

- `id`
- `account_id`
- `type`: `physical_card`, `virtual_card`, `token`, `other`
- `masked_label`
- `last_digits`
- `is_active`
- `created_at`

## Transaction

Операция движения денег.

Поля:

- `id`
- `family_id`
- `account_id`
- `payment_instrument_id`
- `owner_user_id`
- `import_batch_id`
- `bank_transaction_id`
- `occurred_at`
- `amount`: signed amount in account currency
- `currency`: account currency
- `transaction_amount`: original transaction amount from bank export
- `transaction_currency`: original transaction currency from bank export
- `balance_after`
- `direction`: `expense`, `income`, `transfer`
- `flow_type`: `purchase`, `cash_withdrawal`, `cash_expense`, `transfer_to_own_account`, `transfer_to_savings`, `transfer_to_wife`, `person_transfer`, `requisites_payment`, `refund`, `income`, `subscription`, `work_fop`, `other`
- `income_type`: `income`, `refund`, `own_transfer`, `debt`, `other`
- `scope`: `family`, `personal_main_user`, `work_fop`
- `description_raw`
- `description_normalized`
- `bank_category_raw`
- `merchant_id`
- `category_id`
- `subcategory_id`
- `comment`
- `is_cash`
- `is_duplicate_candidate`
- `needs_review`
- `created_at`
- `updated_at`

## Category

Основная категория.

Поля:

- `id`
- `family_id`
- `name`
- `is_system`
- `created_at`

## Subcategory

Подкатегория.

Поля:

- `id`
- `category_id`
- `name`
- `is_system`
- `created_at`

## Merchant

Продавец, магазин, место покупки.

Поля:

- `id`
- `family_id`
- `name`
- `normalized_name`
- `merchant_type`: `store`, `person`, `organization`, `bank_internal`, `unknown`
- `created_at`

## CategorizationRule

Правило автокатегоризации.

Поля:

- `id`
- `family_id`
- `rule_type`: `keyword`, `merchant`
- `pattern`
- `merchant_id`
- `category_id`
- `subcategory_id`
- `priority`
- `is_active`
- `created_at`

## ImportBatch

Метаданные импорта XLSX.

Поля:

- `id`
- `family_id`
- `uploaded_by_user_id`
- `source_filename`
- `period_start`
- `period_end`
- `status`: `draft`, `confirmed`, `deleted`, `expired`
- `total_rows`
- `imported_count`
- `excluded_count`
- `duplicate_count`
- `error_count`
- `uncategorized_count`
- `work_fop_count`
- `savings_count`
- `parser_version`
- `mapping_version`
- `expires_at`
- `created_at`

## ImportPreviewRow

Нормализованная строка draft import до подтверждения.

Поля:

- `id`
- `import_batch_id`
- `row_number`
- `status`: `auto_ready`, `needs_review`, `duplicate_candidate`, `excluded`, `error`
- `reason_codes`
- `occurred_at`
- `amount`
- `currency`
- `transaction_amount`
- `transaction_currency`
- `balance_after`
- `payment_instrument_label`
- `bank_category_raw`
- `description_raw`
- `merchant_name`
- `proposed_category_id`
- `proposed_subcategory_id`
- `proposed_flow_type`
- `proposed_scope`
- `confidence`
- `duplicate_transaction_id`
- `error_message`
- `normalized_payload`
- `created_at`
- `updated_at`

## User Preferences

Настройки пользователя.

Поля:

- `id`
- `user_id`
- `language`: `ru`, `uk`
- `created_at`
- `updated_at`

## Budget

Месячный бюджет семьи.

Поля:

- `id`
- `family_id`
- `month`
- `total_limit`
- `currency`
- `is_draft`
- `created_at`
- `updated_at`

## BudgetLimit

Лимит по категории или подкатегории.

Поля:

- `id`
- `budget_id`
- `category_id`
- `subcategory_id`
- `limit_amount`
- `currency`
- `warning_threshold_percent`

## Notification

Внутреннее уведомление приложения.

Поля:

- `id`
- `family_id`
- `user_id`
- `type`: `budget_warning`, `budget_exceeded`, `import_review_needed`, `cash_reminder`, `insight`
- `title_key`
- `body_key`
- `payload`
- `is_read`
- `created_at`

## Family Settings

Настройки семейного профиля.

Поля:

- `id`
- `family_id`
- `large_transaction_review_threshold`: default `5000`
- `large_supermarket_review_threshold`: default `2500`
- `currency`: `UAH`
- `created_at`
- `updated_at`
