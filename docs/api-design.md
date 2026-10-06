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

## Telegram

Authenticated endpoints derive the application user from the access token:

- `POST /telegram/link-token` - create a 15-minute, single-use Telegram link token. The raw token
  is returned only in this response; `telegram_url` is null if `TELEGRAM_BOT_USERNAME` is unset.
- `GET /telegram/link-status` - return linked state and safe profile display fields.
- `DELETE /telegram/link` - immediately disable the current user's Telegram identity.
- `POST /telegram/webhook` - receive Telegram updates. Validate
  `X-Telegram-Bot-Api-Secret-Token` when configured; production requires the secret when the bot
  token is enabled.

Telegram identity uses immutable `message.from.id` / `callback_query.from.id`. Private chat
commands only; family scope is resolved through `TelegramIdentity -> User -> Family`.

Login and refresh return a short-lived JWT access token in the JSON response. The opaque refresh
token is delivered only as an HttpOnly cookie; JavaScript must not read or persist it. The JWT
subject is the user UUID. The backend loads the user's family from PostgreSQL and does not authorize
from a client-supplied family ID or token family claim. `/auth/me` returns the user and family IDs,
display name, email, language, and family name.

For production, serve the frontend and API on the same site, preferably under a shared custom domain.
If deployment requires a cross-site cookie, configure `AUTH_COOKIE_SAMESITE=none` and
`AUTH_COOKIE_SECURE=true`; use HTTPS and configure the exact frontend origin for credentialed CORS.

## Imports

- `POST /imports/preview` - upload XLSX and create a persisted, categorized and duplicate-checked
  draft preview. The current implementation returns the first page (default 50, maximum 200).
- `GET /imports/{id}/preview` - retrieve the saved draft with `offset`, `limit`, `row_status`,
  `reason_code`, `merchant`, `bank_category`, `proposed_category_id`, and `uncategorized_only`
  filters. Summary status counters describe the full batch; `matching_rows_count` describes the
  filtered result.
- `PATCH /imports/{id}/preview/{row_id}` - update category/subcategory, flow, scope, merchant,
  exclude/include-duplicate decision, or explicit uncategorized decision. Optional
  `apply_to_merchant` extends the correction to matching rows in this draft; `save_rule` explicitly
  creates/updates the Family's normalized exact-merchant rule.
- `POST /imports/{id}/bulk-actions` - apply `assign_category`, `set_scope`, `set_flow_type`,
  `exclude`, `include_duplicate`, `mark_uncategorized`, or `apply_correction` to selected `row_ids`.
  Optional merchant-wide expansion and rule saving use the same fields as the row patch.
- `POST /imports/{id}/confirm?account_id=...` - confirm the reviewed draft into Transactions.
  Unresolved errors block; excluded rows and unaccepted duplicate candidates are skipped.

All import routes derive Family from the authenticated User. Request schemas reject arbitrary status
values and family IDs are not used as authorization inputs. Invalid/foreign row and category IDs
return a validation error. The patch and bulk response include requested/matched/changed counts, a
recomputed full-batch summary, and the affected preview rows.

Preview должен возвращать:

- распознанные операции;
- предполагаемую категорию;
- предполагаемого продавца;
- признак возможного дубля;
- ошибки разбора.

Confirm response and the confirmed ImportBatch retain final summary counters:

- imported count;
- excluded count;
- duplicate count;
- error count;
- uncategorized count;
- work/FOP count;
- savings count.

The saved import review markers are `reviewed_at`, `reviewed_uncategorized`, and
`duplicate_included`. Duplicate matches to existing transactions return transaction summary data
only after a Family-scoped lookup; same-file repeats return the first row number instead.

## Transactions

- `GET /transactions` - authenticated Family-scoped list with server pagination and date, account,
  payment instrument, merchant, category, direction, currency, flow, scope, uncategorized, and review
  filters. Deleted rows are excluded by default.
- `GET /transactions/{id}` - one active transaction; foreign-family and soft-deleted rows return
  the same not-found response.
- `POST /transactions` - authenticated manual expense/income creation; client-supplied family IDs
  are forbidden and the backend stores expense magnitudes as negative and income magnitudes as
  positive `Decimal` values.
- `PATCH /transactions/{id}` - family-scoped update of editable fields while preserving import
  provenance.
- `DELETE /transactions/{id}` - idempotent soft delete with actor and timestamp.

All mutations run through the shared `TransactionService`, which is also used by Telegram manual
entry and review callbacks. Each create/update/delete writes its `AuditLog` record in the same
database transaction. Manual timestamps require an offset and are normalized to UTC; omitted
timestamps use UTC now. See [Transactions API](transactions-api.md) for request, filter, and
soft-delete details.

## Categories

- `GET /categories` - список категорий с подкатегориями.

## Accounts

- `GET /accounts` - authenticated user's active Accounts in their Family, with an
  `is_default` marker from that user's preferences. The endpoint does not accept `family_id` as an
  authorization input.
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

The family is selected from the authenticated user. `family_id` is not a supported authorization
parameter on Web routes; entity IDs such as accounts, transactions, categories, merchants, and import
batches are checked against that family.

## Cash

- `GET /cash/summary` - wallet, approximate balance, and recent cash operations.
- `POST /accounts/cash-wallet` - idempotently create/get the family's active UAH cash wallet.
- `POST /cash/expenses` - add a cash expense through `TransactionService`.
- `POST /cash/transfers` - create paired source/destination legs for a manual withdrawal.
- `POST /cash/imported-withdrawals/{transaction_id}/link` - retain an imported ATM row as the
  source and create only its cash-wallet counterpart.

Linked withdrawal legs are omitted from income/expense analytics and counted once as a family
transfer. Soft deletion applies to both legs atomically; generic edits are blocked.

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
