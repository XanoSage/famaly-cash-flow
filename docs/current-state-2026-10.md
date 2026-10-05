# Current State: 2026-10-05

This state follows the rebaseline and Web identity work already merged into `staging` at
`0f7123b5145a9a95db37e8940435a0957b9b66b7`. Telegram identity work was implemented on
`codex/telegram-identity-linking` at `2fec64838b408fbbafb10698e11673782104eaf2`. `main` is unchanged.

## Verified Working Features

- Web email/password authentication uses normalized email, Argon2, short-lived access JWTs, and
  rotating opaque refresh tokens stored as hashes in PostgreSQL. Authenticated APIs derive Family
  from the persisted User.
- Analytics, categories, transactions, imports, and transaction review are family-scoped.
- XLSX preview, persisted drafts, confirmation, dashboard analytics, and review/category updates
  are present. The Web client has login, a dashboard, recent transactions, and review actions.
- Telegram uses `TelegramIdentity.telegram_user_id` from Telegram's numeric `from.id`. Link tokens
  are random, expire after 15 minutes, are stored as SHA-256 hashes, and are consumed atomically.
- Authenticated Web endpoints create a link, report status, and unlink. The Web account section can
  open/copy a link, display expiry, refresh status on focus, and unlink. TypeScript/Vite production
  build passed; browser interaction beyond rendering the login screen was unavailable here.
- Telegram financial commands and callbacks require a linked identity and private chat. Family is
  derived as `TelegramIdentity -> User -> Family`. `/summary` uses `AnalyticsSummaryService`;
  review mutations use `TransactionReviewService`.
- `/account` stores a validated active family account in `UserPreference`. Manual Telegram expense
  input uses `ManualTransactionService`, Decimal amounts, and aware UTC timestamps.
- Global Telegram family/account IDs have been removed from runtime configuration and Compose.

## Incomplete Features

- Manual Telegram income entry, Telegram notifications, and a Mini App are not implemented.
- Import preview row editing, bulk actions, robust duplicate matching/conflict workflows, and draft
  cleanup need more work. The categorization rule table exists, but the full rule engine is absent.
- Budgets, budget limits, and notifications are not implemented.
- Web has no import UI, router, full transaction-management pages, or frontend test suite.
- Bank-import timestamps remain naive. New Telegram manual transaction timestamps are assigned in
  UTC; browser display policy still needs consistent Europe/Kyiv formatting across the product.
- CI and deployment automation are absent. Login throttling and expired-session cleanup are absent.

## Security Risks and Limits

- Production must set `TELEGRAM_WEBHOOK_SECRET_TOKEN` whenever `TELEGRAM_BOT_TOKEN` is enabled.
  Webhook secret validation is constant-time when configured; a real production webhook has not
  been exercised here.
- Never log link tokens, webhook or bot secrets, Telegram message text, bank rows, transaction
  details, or amounts. The raw link token is returned only from the authenticated create endpoint
  and kept in Web component memory.
- Consumption selects the token hash with `used_at IS NULL`, an unexpired timestamp, and
  `FOR UPDATE`, then repeats those conditions in a conditional update and requires `rowcount == 1`.
  The identity insert and token update commit in the same transaction. SQLite tests prove replay
  rejection but cannot prove PostgreSQL row locks or concurrent consumption; no live PostgreSQL
  test ran.
- The new migration's PostgreSQL upgrade and downgrade SQL have been generated offline. Live
  PostgreSQL migration and constraints remain unverified in this environment.
- The auth migration refuses ambiguous normalized email duplicates; resolve those rows before
  upgrading a database that contains them.

## Technical Debt

- Backend dependencies have open lower bounds and no Python lock file. `frontend/package-lock.json`
  is checked in.
- The backend test client emits a Starlette warning because its httpx integration is deprecated.
- The repository-wide Ruff check has legacy findings; this slice only checks changed files.
- npm reports existing audit findings; they were not broadly upgraded. Vite's dashboard bundle is
  above its 500 kB advisory threshold.
- PostgreSQL/Docker and a real Telegram network test were unavailable locally.

## Local Development Commands

Copy `.env.example` to `.env` and to `backend/.env` for direct backend runs. Set demo credentials;
for Telegram add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, and
`TELEGRAM_WEBHOOK_SECRET_TOKEN`. Do not set family or account IDs for Telegram.

```powershell
# Repository root
docker compose up -d postgres

# Backend
Set-Location backend
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m app.db.seed_system_categories
python -m app.db.seed_demo_dashboard
python -m uvicorn app.main:app --reload

# Frontend, in another terminal
Set-Location frontend
npm ci
npm run dev -- --host localhost

# Backend verification
Set-Location backend
python -m pytest -q
python -m alembic history --verbose
python -m alembic upgrade head --sql

# Frontend production TypeScript and Vite build
Set-Location frontend
npm run build
```

For Telegram, sign in to Web, create a link in the Telegram section, and complete `/start <token>` in
a private chat. Use a public HTTPS tunnel for the webhook; see
[Telegram Local Checklist](telegram-local-checklist.md).

## Verification Results

Commands run for this slice (Windows PowerShell):

- `backend\\.venv\\Scripts\\python.exe -m pytest -q`: **107 passed, 1 warning in 5.09s**. The
  warning is Starlette's deprecated httpx test-client integration. The API tests use SQLite.
- Collection comparison: staging at `0f7123b` collected **121** tests; the Telegram branch collected
  **107**. No test files were deleted; five Telegram test modules were refactored and
  `test_telegram_identity.py` was added. Per-module collected counts changed as follows: dispatcher
  13→8, manual 6→6, review 14→3, summary 3→1, webhook 11→5, identity 0→10. That is 45 old node
  IDs no longer present and 31 new IDs (net −14). The manual parser's two test names remain; the
  other prior function names were rewritten or consolidated, not mechanically renamed. There were
  no pytest configuration or shared fixture changes and no parameterized Telegram cases removed;
  the new unlinked-summary webhook test has private/group cases. Auth tests and their parameterized
  security cases are unchanged.
- `backend\\.venv\\Scripts\\ruff.exe check --select E,F,I <25 changed Python files>`:
  **passed**. `ruff.exe format --check <same files>`: **passed, 25 files already formatted**.
- `backend\\.venv\\Scripts\\python.exe -m pip check`: **No broken requirements found**.
- `python -m alembic history --verbose` and `python -m alembic heads`: **passed**; the chain is
  linear and `202610050002` is the single head.
- `python -m alembic upgrade head --sql`: **passed**, generated PostgreSQL SQL for the full chain
  through `202610050002`. This is offline SQL generation, not a live migration.
- `npm ci` first failed with `UNABLE_TO_VERIFY_LEAF_SIGNATURE`. Retried successfully with Node's
  system CA support (`node.exe --use-system-ca ...\\npm-cli.js ci --prefer-offline`): **109 packages
  installed**. npm reported **5 vulnerabilities** (1 low, 1 moderate, 3 high), deprecated Recharts
  2.x, and an esbuild install-script warning. No audit fixes were applied.
- `npm run build`: **passed** (`tsc -b` and Vite; 2,199 modules). Output: **618.32 kB**
  (178.74 kB gzip), above Vite's 500 kB advisory threshold. Two other invocations failed in
  `vite:build-html` while emitting `index.html` under a relative path escaping the frontend
  directory. `npm run build -- --debug` and repeated plain builds, including an isolated final run,
  passed without source/config changes. This intermittent Windows/Vite/Rollup failure remains
  unexplained.
- Local synthetic SQLite backend started and `GET /api/v1/health` returned **200**. The in-app
  browser rendered the login page, but its tab controls were read-only in this environment, so Web
  login/link UI interaction was not verified. Backend API linking and Telegram flows are covered by
  tests.
- `docker`, `docker-compose`, and `psql` are unavailable on PATH. No live PostgreSQL migration,
  PostgreSQL concurrency test, or real Telegram Bot API smoke test ran. Bot credentials and a public
  HTTPS webhook were not configured.

## Recommended Next Slice

Finish the import review path: add the missing preview-row editing and bulk-action API/UI, then
verify duplicate matching and conflict handling against representative bank statements. Keep the
existing FastAPI/PostgreSQL/SQLAlchemy and React/TypeScript architecture.
