# Telegram Bot Plan

## Why This Matters

Telegram Bot API 10.x adds stronger building blocks for bot-first workflows:

- Rich messages can make weekly summaries, category tables, and review queues easier to read inside Telegram.
- Mini Apps remain a good future path for opening the Family Cash Flow dashboard directly from a bot.
- Inline buttons and ordinary bot commands are enough for the first useful MVP before adopting newer rich-message features.

Official docs:

- https://core.telegram.org/bots/api
- https://core.telegram.org/bots/features

## Product Fit

For Family Cash Flow, Telegram should start as a quick family inbox, not as a second full frontend.

Good first workflows:

- `/summary` returns income, expenses, savings, cash flow, and review count.
- `/review` returns transactions where `needs_review=true`.
- Inline buttons let a user mark an operation as reviewed.
- Category buttons/select-like flows let a user assign a category and clear `needs_review`.
- Later, plain text messages like `АТБ 450 еда` can create manual transaction drafts.

## MVP Slices

1. Backend webhook skeleton.
   - Add `POST /api/v1/telegram/webhook`.
   - Accept Telegram update JSON.
   - Verify `X-Telegram-Bot-Api-Secret-Token` when configured.
   - Return `{"ok": true}` while handlers are not implemented.

2. Bot configuration.
   - Add env vars for bot token and webhook secret.
   - Keep token out of git.
   - Add local documentation for setting webhook later.

3. Read-only bot commands.
   - `/start`
   - `/summary`
   - `/review`

4. Review queue actions.
   - Mark reviewed.
   - Assign category and clear review flag.

5. Manual transaction draft.
   - Parse simple text input.
   - Create draft/manual transaction with `needs_review=true` if parsing is uncertain.

6. Rich messages and Mini App.
   - Use rich messages for weekly reports when SDK support is stable.
   - Consider a Telegram Mini App wrapper around the existing React dashboard.

## Current Decision

Start with webhook infrastructure and tests, then build bot behavior in small slices.
Do not depend on the newest Telegram SDK features until the Python library support is stable.

## Local Setup Notes

- Set `TELEGRAM_DEFAULT_FAMILY_ID` in backend `.env` to the demo seed family id before testing `/summary`.
- This is a temporary MVP shortcut until Telegram users are linked to Family Cash Flow users/families in the database.

## Implemented

- Webhook skeleton: `POST /api/v1/telegram/webhook`.
- Optional Telegram webhook secret verification.
- Pure dispatcher for `/start` command, covered by tests.
- Outgoing Telegram `sendMessage` client for dispatcher replies.
- `/summary` command backed by `AnalyticsSummaryService` and `TELEGRAM_DEFAULT_FAMILY_ID`.
- `/review` command lists latest `needs_review=true` transactions for `TELEGRAM_DEFAULT_FAMILY_ID`.
