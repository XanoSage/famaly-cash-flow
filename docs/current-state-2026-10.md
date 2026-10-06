# Current State (2026-10-06)

The Cash Ledger work is on `codex/cash-ledger`, based on `staging` commit
`6b918e1d490ee9b29e3cb65e01169dc8b9a6c2bb`, which contains Everyday Transactions. The branch has
not been merged into `staging` or `main`; `main` was not modified.

## Verified Working Features

- The stack remains Python/FastAPI, PostgreSQL, SQLAlchemy 2, Alembic, Pytest,
  React/TypeScript/Vite. PostgreSQL is the application source of truth; monetary values use
  `Decimal` and PostgreSQL `NUMERIC`.
- Web authentication, persistent refresh sessions, Telegram identity linking, and family-scoped
  authenticated APIs are present on the branch base. Web and Telegram derive the same application
  user and Family; API routes do not accept `family_id` as an authorization input.
- XLSX preview/review/confirmation and everyday transaction list/create/edit/soft-delete flows are
  implemented. Transaction changes write audit records atomically and keep imported descriptions.
- Cash Ledger adds one idempotently created active family cash wallet in UAH. There is no separate
  balance table; the approximate balance is the sum of active wallet transaction amounts.
- A manual withdrawal creates two atomic, auditable legs: a negative source-account leg and a
  matching positive wallet leg. Withdrawal legs are transfers, not family expenses or income. The
  family transfer metric counts the paired withdrawal once.
- Linking an eligible imported ATM row preserves the imported bank debit and creates only the
  wallet-side counterpart. This avoids a second bank debit.
- A cash purchase is one ordinary wallet expense, so it reduces the approximate wallet balance and
  counts as a family expense once. Linked withdrawal legs cannot be edited separately; soft-deleting
  either leg soft-deletes both and audits both changes in one database transaction.
- The Web Cash page supports RU/UK, wallet setup, cash withdrawal, cash expense with category/scope/
  comment, recent wallet activity, and linking an imported ATM row from Transactions.
- Telegram `/cash <amount> <description>` records a cash expense through the same
  `TransactionService` used by Web. If the wallet is missing, the bot directs the user to create it
  in Web.

## Implementation Plan Status

| Phase | Status | Current evidence |
| --- | --- | --- |
| 0. Repository/branch setup | Complete | `codex/cash-ledger` is based on the staging merge; `main` is untouched. |
| 1-3. Skeleton and database | Complete | FastAPI/React app, PostgreSQL models, and a single Alembic migration head. |
| 4. Auth MVP | Complete in code | Web auth and persistent Telegram identity linking; family scope comes from the persisted user. |
| 5-6. Parser/import preview | Complete in code | Synthetic XLSX tests; persisted preview, duplicate review, and bulk/row review actions. |
| 7. Categorization | Partial | Rules and current mappings exist; breadth and heuristics remain incomplete. |
| 8. Import confirmation | Complete in code | Web upload/review/confirm path and backend tests. |
| 9. Transactions API | Complete in code | Family-scoped CRUD, audit, validation, and soft delete. |
| 10. Analytics API | Complete for current endpoints | Summary, categories, merchants, timeline, savings, work/FOP and insights. Cash withdrawals now remain outside expense/income and count once as transfers. |
| 11. Frontend skeleton | Partial | Authenticated React shell and page navigation; no rendered-component test harness. |
| 12. Import UI | Complete in code | Upload, review, row edit, bulk actions, and confirmation. |
| 13. Operations/dashboard UI | Partial | Transactions and Cash Ledger UI are implemented; broader dashboard charts/blocks and browser tests remain. |
| 14. Budgets/notifications | Not started | Budget limits and budget notifications are absent. |
| 15. DevOps | Partial | GitHub Actions covers backend, PostgreSQL migrations/integration, and frontend. Image publishing/deployment are absent. |

## Incomplete Features

- Budgets, category limits, budget notifications, and Telegram notifications/Mini App.
- Broader categorization rules and a product-wide family timezone policy. Manual Web timestamps are
  converted from browser-local time to UTC; Telegram cash entries default to UTC now. Bank import
  wall-time semantics are unchanged.
- A forgotten-cash reminder and richer cash-history controls. The wallet balance remains an
  estimate because unrecorded cash spending cannot be inferred.
- Rendered React/browser tests. Frontend tests cover API calls and pure helpers, not actual component
  interactions or browser-to-PostgreSQL flows.
- A live PostgreSQL migration/integration run on this Windows machine. PostgreSQL-marked tests are
  skipped locally because Docker is unavailable; branch CI is the live database verification.
- Live Telegram Bot API/webhook interaction. Telegram behavior is tested without contacting the
  external Bot API.

## Security Risks And Technical Debt

- `audit_logs` stores before/after financial values and descriptions. Treat those payloads as
  sensitive database data and do not emit them or transaction details to application logs.
- Authenticated endpoints scope records through the user’s Family, but there is no fine-grained
  family role/permission model.
- The Starlette test client emits a deprecation warning for its current `httpx` integration.
- Vite succeeds but warns that the minified JavaScript chunk exceeds 500 kB.
- Repository-wide Ruff still reports 21 findings in untouched baseline files (16 `E501`, 5
  `I001`), and its formatter reports 25 untouched files would be reformatted. The changed Python
  files pass both CI's changed-file checks.
- Docker/PostgreSQL are unavailable locally, so Compose startup and live local migration checks
  could not be run.
- No production deployment, real bank API, or live Telegram service was used.

## Local Development Commands

Configure `.env` and `backend/.env` from `.env.example` and point the backend at local PostgreSQL.
Set Telegram bot configuration only when exercising the webhook; do not use global family/account
IDs.

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

# Frontend, in a second terminal
Set-Location frontend
npm ci
npm run dev -- --host localhost

# Verification
Set-Location backend
python -m pytest -q
python -m alembic heads
Set-Location ..\frontend
npm test
npm run build
```

PostgreSQL integration tests require a disposable database whose name ends in
`_integration_test`. See [Testing](testing.md) for the required environment variables and safe
setup instructions.

## Verification Results On This Branch

Commands were run in Windows PowerShell from the listed directories.

| Directory | Command | Result |
| --- | --- | --- |
| `backend` | `.venv\Scripts\python.exe -m pytest -q` | **166 passed, 7 skipped, 1 warning.** Skips are PostgreSQL-only tests; the warning is Starlette's `httpx` TestClient deprecation. |
| `backend` | Ruff `check --select E,F,I` on changed Python files | **Passed.** |
| `backend` | Ruff `format --check` on changed Python files | **Passed:** 25 files already formatted. |
| `backend` | `.venv\Scripts\python.exe -m alembic heads` | **One head:** `202610060002`. |
| `backend` | `.venv\Scripts\python.exe -m alembic upgrade head --sql` | **Passed:** PostgreSQL SQL generated offline through `202610060002`; no database connection was made. |
| `backend` | `.venv\Scripts\python.exe -m ruff check --select E,F,I --statistics --output-format concise app tests` | **Failed on untouched baseline files:** 21 findings (16 `E501`, 5 `I001`). Changed-file checks pass. |
| `backend` | `.venv\Scripts\python.exe -m ruff format --check app tests` | **Failed on untouched baseline files:** 25 would be reformatted; all changed Python files pass. |
| `frontend` | `npm.cmd test` | **14 passed, 0 failed.** |
| `frontend` | `npm.cmd run build -- --debug` | **Passed:** TypeScript and Vite; 2,212 modules transformed; JS 705.17 kB (200.44 kB gzip), CSS 21.28 kB. Vite emitted the >500 kB chunk warning. An earlier parallel invocation failed in Vite's HTML asset naming; the isolated build completed successfully. |
| repository root | `Get-Command docker -ErrorAction SilentlyContinue` | **Unavailable:** no Docker CLI; Compose and live local PostgreSQL checks could not run. |
| repository root | `git diff --check` | **Passed.** |
| GitHub Actions | `codex/cash-ledger` branch run | Pending push/verification. |

## Recommended Next Task

After this branch's PostgreSQL CI is green, implement the **Budget Foundation** as a backend-first
slice: Alembic-backed monthly family budget and category-limit models, family-scoped API/service
operations using `Decimal`, and PostgreSQL plus unit tests. Defer budget notifications and broader
dashboard redesign to later slices.
