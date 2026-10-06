# Current State (2026-10-06)

This work is on `codex/everyday-transactions`, based on `staging` at `15c061b` (the PostgreSQL
integration CI merge). Neither `staging` nor `main` was modified as part of this feature work.

## Verified and Implemented

- Stack remains Python/FastAPI, PostgreSQL, SQLAlchemy 2, Alembic, Pytest, React, TypeScript, and
  Vite. PostgreSQL is the application source of truth. Web and Telegram resolve the same persisted
  application user and Family.
- Web authentication, rotating refresh sessions, Telegram account linking, authenticated family
  scope, import preview/review/confirmation, dashboard analytics, and account/category APIs were
  already present on the base branch.
- `TransactionService` now centralizes manual transaction creation, editing, review changes, and
  soft deletion. Web mutation routes, Telegram manual entry, Telegram `/income`, and Telegram review
  callbacks use that service.
- Transaction routes support authenticated list, single read, create, update, and idempotent soft
  delete. They derive family scope from the active persisted user and validate account/category
  membership. Request amounts are positive magnitudes; stored expense amounts are negative and
  income amounts positive `Decimal` values.
- Mutation audit rows are written atomically in `audit_logs`. Manual timestamps require an offset
  and are normalized to UTC; an omitted timestamp uses UTC now. Editing display text preserves
  imported source descriptions through `description_override`.
- Soft-deleted transactions remain stored with `deleted_at` and `deleted_by_user_id`, are hidden
  from normal transaction reads/lists, and are excluded from analytics. Unit/API tests verify the
  audit record, idempotence, and analytics exclusion.
- The Web Transactions page supports RU/UK localization, expense/income create and edit, confirmed
  soft delete, date/account/category/direction/scope/review filters, and server pagination. It uses
  the existing authenticated fetch/refresh path. Decimal strings are formatted without converting
  amounts to floating point.
- Telegram continues to use the selected user's active default account. `/income 25000 Зарплата`
  creates a positive income transaction through the shared service; uncategorized manual entries
  are marked for review.

## Implementation Plan Status

| Phase | Status | Current evidence |
| --- | --- | --- |
| 0. Repository/branch setup | Complete | Feature branch is based on `staging`; `main` is untouched. |
| 1. Monorepo skeleton | Complete | Backend, frontend, infrastructure, and docs are present. |
| 2. Backend skeleton | Complete | FastAPI app and pytest suite exist. |
| 3. Database/migrations | Implemented; migration SQL checked | Alembic has one head, `202610060001`; offline PostgreSQL SQL generation succeeds. Local PostgreSQL/Docker is unavailable. |
| 4. Auth MVP | Complete in code | Web auth and persistent Telegram identity linking are on the base branch; family derives from the persisted user. |
| 5. XLSX parser | Complete | Parser and synthetic XLSX tests exist. |
| 6. Import preview backend | Complete | Preview persistence, filters, review, duplicate decisions, and confirmation are implemented. |
| 7. Categorization | Partial | Rules and current mappings work; planned categorization breadth/heuristics remain incomplete. |
| 8. Import confirmation | Complete in code | Web upload/review/confirm flow is implemented; no live browser-to-PostgreSQL run was made here. |
| 9. Transactions API | Complete in code | Family-scoped list/get/create/update/soft-delete, audit, validation, and filters are implemented and covered by backend tests. PostgreSQL integration is still pending CI. |
| 10. Analytics API | Complete for current endpoints | Existing summary, timeline, category, merchant, savings, work/FOP, and dashboard endpoints remain; deletion exclusion is regression-tested. |
| 11. Frontend skeleton | Partial | Authenticated React shell and query-string page navigation work; no full routing framework or rendered-component test harness. |
| 12. Import UI | Complete in code | Upload, review, edit, bulk actions, and explicit confirmation are implemented. |
| 13. Operations/dashboard UI | Partial | Dashboard and everyday transaction management are implemented. A dedicated cash short form and broader cash workflow remain. |
| 14. Budgets/notifications | Not started | Budget limits and in-app budget notifications are absent. |
| 15. DevOps | Partial | GitHub Actions exists on the base branch; image publishing/deployment are absent. This feature branch's CI run must be checked after push. |

## Incomplete Features

- Budgets, budget notifications, and Telegram notifications/Mini App.
- Broader categorization mappings/heuristics and a product-wide policy for naive bank-statement wall
  times. Bank import timestamp semantics were not changed; manual Web/Telegram times are UTC-aware.
- Dedicated cash withdrawal/transfer entry flow. The transaction form can record a cash-account
  operation, but does not implement a cash balance workflow.
- Rendered React component/browser tests. Frontend tests exercise API requests and pure request,
  timestamp, pagination, and Decimal-string formatting behavior.
- Live PostgreSQL execution of the new migration and integration case on this machine. Six
  PostgreSQL-marked tests were skipped locally because there is no local Docker/PostgreSQL setup.
- Live Telegram Bot API/webhook interaction; Telegram tests cover parsing, dispatch, family scope,
  and shared-service persistence without contacting Telegram.

## Security Risks and Technical Debt

- `audit_logs` contains before/after financial values and descriptions in PostgreSQL. Restrict access
  to the same family/user authorization boundaries; do not emit payloads to application logs.
- Bank imports retain the parser's existing wall-time semantics while manual entries are normalized
  to UTC. Cross-boundary reporting/date filters need a documented family timezone policy.
- No backend dependency lock file is checked in. `frontend/package-lock.json` is checked in.
  Dependency freshness and the advisories reported during the earlier `npm ci` audit were not
  addressed in this feature slice.
- The FastAPI/Starlette test client emits a deprecation warning for its current `httpx` integration.
- Vite succeeds but reports a minified JavaScript chunk above 500 kB. Bundle splitting is deferred.
- Docker is not installed in the current Windows environment, so Compose validation, local database
  startup, live migration, and PostgreSQL tests could not run here.
- No live browser interaction, production deployment, or real Telegram webhook request was run.

## Local Development Commands

Configure `.env` and `backend/.env` from `.env.example` with a local PostgreSQL URL. For Telegram,
configure the bot token, username, and webhook secret; do not configure default family/account IDs.

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

# Frontend in a second terminal
Set-Location frontend
npm ci
npm run dev -- --host localhost

# Backend verification
Set-Location backend
python -m pytest -q
python -m alembic heads

# Frontend verification
Set-Location frontend
npm test
npm run build
```

PostgreSQL integration tests require a disposable database whose name ends in `_integration_test`.
See [Testing](testing.md) for the required environment variables and safe setup instructions.

## Commands Executed for This Feature

Commands were run in Windows PowerShell. Exact final results are recorded here after the last test
run and branch CI check.

| Directory | Command | Result |
| --- | --- | --- |
| `backend` | `.venv\Scripts\python.exe -m pytest -q` | **153 passed, 6 skipped, 1 warning.** The skipped tests require local PostgreSQL. Warning: Starlette deprecates its `httpx` TestClient integration. |
| `backend` | `.venv\Scripts\python.exe -m pip check` | **Passed:** no broken requirements found. |
| `backend` | Ruff `E,F,I` and format checks on all changed Python files | **Passed.** |
| `backend` | `.venv\Scripts\python.exe -m ruff check --select E,F,I --statistics app tests` | **Failed on untouched baseline files:** 24 findings (19 line-too-long, 5 unsorted imports). |
| `backend` | `.venv\Scripts\python.exe -m ruff format --check app tests` | **Failed on untouched baseline files:** 28 would be reformatted; all changed Python files pass. |
| `backend` | `.venv\Scripts\python.exe -m alembic heads` | **One head:** `202610060001`. |
| `backend` | `.venv\Scripts\python.exe -m alembic upgrade head --sql` | **Passed:** offline PostgreSQL migration SQL generated through the new head; no database connection was made. |
| `frontend` | `npm.cmd test` | **13 passed, 0 failed.** Node built-in test runner. |
| `frontend` | `npm.cmd run build` | **Passed:** TypeScript and Vite; 2,211 modules transformed; JS 692.91 kB (198.16 kB gzip), CSS 20.06 kB. Vite emitted the >500 kB chunk warning. |
| repository root | `docker --version`; `docker compose config --quiet` | **Unavailable:** Docker executable is not installed. |
| repository root | `gh auth status` | **Unavailable:** the configured GitHub CLI token is invalid. The feature branch CI result still needs a verifiable check after push. |

`git diff --check` passed. No database data, Telegram service, or production deployment was changed.

## Recommended Next Task

Implement the **cash-entry workflow**: add a focused cash expense/withdrawal entry flow that uses
`TransactionService`, models cash withdrawals and subsequent cash spending without double-counting
analytics, adds Alembic changes only if the existing schema cannot represent the flow, and covers
family authorization, Decimal accounting, audit behavior, and analytics with tests. Keep Web and
Telegram on the shared domain service; do not start budgets in that slice.
