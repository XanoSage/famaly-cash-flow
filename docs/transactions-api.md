# Transactions API

Transaction list and mutation endpoints are under `/api/v1/transactions`. Every route requires an
authenticated Web user. The backend resolves the Family through the persisted user; `family_id` is
not an authorization input. Transaction, account, category, merchant, and payment-instrument IDs are
checked against that Family.

## List and read

`GET /transactions` returns a newest-first page. It supports `offset` (default `0`) and `limit`
(default `50`, maximum `200`) with optional filters:

- `occurred_from`, `occurred_to` (ISO timestamp; the Web sends UTC instants derived from local date
  boundaries);
- `account_id`, `payment_instrument_id`, `merchant_id`, `category_id`;
- `uncategorized`, `direction`, `transaction_currency`, `flow_type`, `scope`, `needs_review`;
- `include_deleted` (default `false`; deleted rows are excluded by default).

`GET /transactions/{id}` returns one active transaction or a family-scoped 404. Soft-deleted and
foreign-family transactions are both hidden.

## Create, update, and delete

`POST /transactions` accepts `direction` (`expense` or `income`), a positive `amount` with at most
two fractional digits, `account_id`, optional offset-aware `occurred_at`, merchant/description,
category/subcategory, scope, and comment. The service derives the Family and creator from the
authenticated user, validates active account/category membership, and applies the sign convention:
expense amounts are stored negative, income amounts positive. An omitted timestamp uses current UTC.
An uncategorized manual operation is marked for review.

`PATCH /transactions/{id}` updates supported classification and display fields. The request amount
is a positive magnitude; the service stores its sign based on direction. Imported provenance fields
are immutable through this endpoint. Editing a display description preserves the raw bank/import
description.

`DELETE /transactions/{id}` is an idempotent soft delete. It sets `deleted_at` and
`deleted_by_user_id`, writes an audit row in the same database transaction, returns `204`, and keeps
the original transaction available for audit/history. Deleted transactions are excluded from the
default list and analytics.

Create, update, and delete audit records are stored in `audit_logs` with family, actor, entity, action,
and before/after JSON values. Amounts and timestamps are serialized as strings; audit contents remain
sensitive financial data and must not be emitted to application logs.

## Shared Telegram behavior

Web transaction mutations, Telegram manual expense entry, Telegram `/income <amount> <description>`,
and Telegram review edits use `TransactionService`. Telegram resolves the linked application user
and family first and selects that user's active default account. Manual Telegram timestamps are
created in UTC. Imported bank wall times keep their existing parser semantics; a product-wide bank
timezone policy remains open.

The Web Transactions page supports RU/UK labels, date/account/category/scope/direction/review filters,
server pagination, expense/income creation, editing, and confirmed soft deletion. It uses the same
authenticated API client and refresh behavior as the rest of the Web app.

## Cash Ledger

The authenticated `/api/v1/cash/summary` returns the family's active UAH cash wallet, the approximate
balance (the sum of active wallet transactions), and the 15 most recent wallet operations. If the
wallet does not exist, the summary returns `wallet: null` and a zero balance. The Web can create it
idempotently with `POST /api/v1/accounts/cash-wallet`.

`POST /api/v1/cash/transfers` records a withdrawal as two rows in one database transaction: a
negative `cash_withdrawal` transfer leg on the selected non-cash account and a matching positive leg
on the wallet. It is excluded from family income/expense totals; family transfer volume/count includes
the logical withdrawal once. `POST /api/v1/cash/imported-withdrawals/{transaction_id}/link` links an
eligible imported ATM row and adds only its wallet-side counterpart, preserving the bank row and
avoiding a second debit.

`POST /api/v1/cash/expenses` records a normal negative expense on the wallet. Its expense appears
once in family analytics and reduces the approximate wallet balance. Transfer pairs cannot be
edited through the generic transaction patch route; soft-deleting either leg soft-deletes both legs
and writes both audit rows atomically.
