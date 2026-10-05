# Telegram Bot Plan

## Product Role

Telegram is a core daily client for fast family finance tasks. Web remains the home for XLSX imports,
deep transaction review, settings, detailed analytics, and Telegram account linking.

Telegram supports:

- quick manual expense entry (income entry is a follow-up);
- short summaries;
- a review queue with mark-reviewed and category assignment actions;
- selecting a persisted default account.

Telegram notifications and a Mini App remain future work.

## Identity and Access

The authenticated Web user requests a 15-minute, single-use link. The database stores only a
SHA-256 token hash. The private `/start <token>` flow maps Telegram's numeric `from.id` to the
application User. The Family is loaded through that User. Telegram usernames are display metadata;
chat IDs are reply destinations, not identity.

Financial commands and callbacks work only in private chats. Webhook requests validate
`X-Telegram-Bot-Api-Secret-Token` when configured; production requires the secret when the bot is
enabled. There are no global family or account environment IDs.

## Implemented

- Webhook at `POST /api/v1/telegram/webhook`.
- Authenticated Web link-token, link-status, and unlink endpoints.
- Web Telegram account section that creates, opens, copies, refreshes, and revokes links.
- `/start` linking using a hashed, expiring, one-time token.
- `/summary` through the shared `AnalyticsSummaryService`.
- `/review`, `/done`, category correction callbacks through shared
  `TransactionReviewService`.
- `/account` and family-scoped account selection.
- Manual expense text such as `АТБ 450 еда` through `ManualTransactionService`, using Decimal and
  an aware UTC timestamp.
- Private-chat-only handling for financial commands; sender mapping uses numeric `from.id`.

## Configuration

Set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` (username without `@`), and
`TELEGRAM_WEBHOOK_SECRET_TOKEN`. Never configure a family or account ID in Telegram environment
settings. See [Telegram Local Checklist](telegram-local-checklist.md) for setup.

## Remaining Work

- Add manual income entry.
- Decide whether to send notifications after cash withdrawals or budget thresholds.
- Consider richer summaries and a Telegram Mini App after core workflows are stable.
- Verify row-lock and conditional token consumption against live PostgreSQL.

## Reference

- https://core.telegram.org/bots/api
- https://core.telegram.org/bots/features
