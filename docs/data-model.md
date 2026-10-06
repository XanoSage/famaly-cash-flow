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
- `email` - trimmed and lowercased; globally unique for the one-family-per-user MVP
- `password_hash` - Argon2 encoded hash
- `display_name`
- `is_active`
- `created_at`

## AuthSession

Persistent refresh session for one application user.

Fields:

- `id`
- `user_id`
- `refresh_token_hash` - SHA-256 of a random opaque refresh token; the raw token is only sent in an
  HttpOnly cookie
- `expires_at`
- `revoked_at`
- `created_at`
- `updated_at`

## TelegramIdentity

One active Telegram account mapping per application user and one application user per immutable
Telegram sender ID.

Fields:

- `id`
- `user_id` - application User foreign key
- `telegram_user_id` - unique Telegram `from.id` (never the chat ID or username)
- `private_chat_id` - destination for private bot replies
- `username`, `first_name`, `last_name` - display metadata only
- `linked_at`, `last_seen_at`, `is_active`
- `created_at`, `updated_at`

Database uniqueness constraints cover both `user_id` and `telegram_user_id`.

## TelegramLinkToken

Short-lived one-time account-link token. PostgreSQL stores only its SHA-256 hash.

Fields:

- `id`
- `user_id`
- `token_hash`
- `expires_at`
- `used_at`
- `created_at`, `updated_at`

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
- `amount`: signed `Decimal`/PostgreSQL `NUMERIC(14, 2)` in account currency; expenses are negative
  and incomes are positive
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
- `description_override`: user-edited display text; does not replace bank/import provenance
- `bank_category_raw`
- `merchant_id`
- `category_id`
- `subcategory_id`
- `comment`
- `is_cash`
- `is_duplicate_candidate`
- `needs_review`
- `deleted_at`
- `deleted_by_user_id`
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
- `auto_ready_count`
- `needs_review_count`
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
- `duplicate_included` - explicit user decision to import a matched duplicate candidate
- `reviewed_uncategorized` - explicit decision to import without a category
- `reviewed_at` - timestamp of a user review edit
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
- `default_account_id` - nullable account selection; service validation requires an active account
  in the user's family
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

## AuditLog

Audit record for transaction mutations. Create/update/delete rows are written atomically with the
transaction change. `before_payload` and `after_payload` hold a minimal snapshot; financial content
in these fields is sensitive.

Поля:

- `id`
- `family_id`
- `user_id`
- `entity_type`: currently `transaction`
- `entity_id`
- `action`
- `before_payload`
- `after_payload`
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
