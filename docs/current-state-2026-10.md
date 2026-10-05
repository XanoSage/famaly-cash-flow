# Current State (2026-10-05)

The source-of-truth branch is `staging`. This task started from staging commit
`afc8a82978c58e2237f14f672a25e7294e6ba016`, which includes the merged Web Import Review UI from
`codex/web-import-review-ui`. The CI and PostgreSQL integration work is on the short-lived branch
`codex/ci-postgres-integration`; `main` was not changed. This document records the staging
implementation and the CI branch's verification status.

## Verified Working Features

- FastAPI, SQLAlchemy 2, Alembic, PostgreSQL configuration, React, TypeScript, and Vite are present.
  The complete backend test suite passes against its test setup, which uses SQLite for API tests.
- Web email/password authentication, Argon2 password hashes, short-lived access JWTs, rotating
  opaque refresh tokens stored as hashes in PostgreSQL, and authenticated `/auth/me` are implemented.
  Family scope is derived from the persisted User, not a request-supplied `family_id`.
- Telegram identity linking persists the numeric Telegram user ID and resolves the linked User and
  Family. Financial Telegram handling and Web share application/domain services. Link tokens are
  hashed, expire, and are single-use. The Telegram Bot API and production webhook were not exercised.
- Dashboard analytics, category APIs, transaction list/review APIs, Telegram link management, and
  the existing authenticated Web dashboard are implemented.
- XLSX preview persists a draft. Categorization rules, conservative exact duplicate checks, row
  review, bulk actions, and confirmation are implemented in backend services. The Web Import Review
  screen now supports upload, server-filtered/paged preview, RU/UK labels, row edits, selected-row
  bulk actions, duplicate comparison/decisions, account selection, explicit confirmation, and a
  confirmed-result state. Refreshing a confirmed batch shows its result without confirming again.
- `GET /api/v1/accounts` returns active accounts for the authenticated user's Family, ordered by
  name, with the current user's default-account marker. It does not accept a client Family ID.
- Import batch IDs are the only financial-flow state placed in the URL. Transaction rows and draft
  contents are not written to browser storage. Upload and confirmation are explicit user actions.
- Account API tests cover active/default accounts, ignored foreign-Family input, and unauthenticated
  access. Frontend tests cover API request wiring and pure review-flow decisions.
- GitHub Actions now defines separate backend, PostgreSQL integration/migration, and frontend jobs.
  The PostgreSQL suite uses a dedicated database ending in `_integration_test`, checks the Alembic
  head, and refuses to run unless explicitly enabled. CI marks it required.
- PostgreSQL integration cases exercise refresh-token rotation/replay/revocation and concurrent
  refresh; Telegram link-token replay, concurrency, and transaction rollback; import review and
  confirmation with exact `Decimal` persistence; and PostgreSQL unique/FK constraints. Local
  PostgreSQL is unavailable on this machine, so these cases skip locally; a successful hosted CI
  run is needed before treating PostgreSQL behavior as verified.
- `AGENTS.md` contains the repository's development constraints and read-before-edit documentation
  list.

## Implementation Plan Status

| Phase | Status | Verified state |
| --- | --- | --- |
| 0. Repo and branch setup | Complete | `main`, `staging`, and feature-branch workflow exist. This task branched from `staging`; no merge to `main`. |
| 1. Monorepo skeleton | Complete | Backend, frontend, infra, and docs are present. |
| 2. Backend skeleton | Complete | FastAPI app, health route, and pytest suite exist. |
| 3. Database and migrations | Implemented; live verification pending | PostgreSQL Compose config, SQLAlchemy models, seeds, and a linear Alembic chain exist. Offline SQL generation passes. CI now performs a real upgrade and latest-revision downgrade/upgrade against PostgreSQL; its result must be checked after push. |
| 4. Auth MVP | Complete in code | Web login, refresh/logout, current user, persistent sessions, and authenticated family scope are implemented and covered by backend tests. |
| 5. XLSX parser spike | Complete | Synthetic XLSX parser coverage and normalized bank-row handling exist. |
| 6. Import preview backend | Complete | Draft creation, persistence, filters, errors, and duplicate candidates are implemented. |
| 7. Categorization engine | Partial | Normalized system/Family rules, priorities, field conflict handling, and a small system bank-category seed exist. Broad mappings and all planned transfer/savings/FOP heuristics are not complete. |
| 8. Import confirmation | Complete in code | Backend review/confirmation services and the Web upload-review-confirm flow exist. Full browser-to-PostgreSQL confirmation was not exercised. |
| 9. Transactions API | Partial | Family-scoped list and patch/review exist; create, get-one, soft-delete, and audit-log scope from the plan are not all implemented. |
| 10. Analytics API | Complete for current MVP endpoints | Summary, timeline, category, merchant, dashboard, insights, savings, and work/FOP endpoints exist and are tested. |
| 11. Frontend skeleton | Partial | Authenticated React shell, login, API client, localization, dashboard, and query-string page navigation exist. There is no full routing framework or complete page set. |
| 12. Import UI | Complete in code | Upload → review/edit/bulk → account select → explicit confirmation is implemented. UI interaction against a live database remains unverified. |
| 13. Operations and dashboard UI | Partial | Dashboard and review list are present; full transaction management, manual transaction, and cash-entry screens remain. |
| 14. Budgets and notifications | Not started | Budget limits and warning/notification flows are absent. |
| 15. DevOps MVP | Partial | Local Compose, a backend Dockerfile, and GitHub Actions checks exist. Docker image publishing and a verified deployment path are absent. The PostgreSQL workflow run is pending verification. |

## Incomplete Features

- Budget creation/limits, budget notifications, Telegram notifications, Telegram income-entry flow,
  and a Telegram Mini App.
- Full categorization breadth, transaction create/delete/audit APIs, and complete everyday Web
  transaction-management screens.
- Parse-error date/amount correction; currently users can exclude invalid rows.
- Draft-expiration cleanup execution. Draft expiry metadata exists.
- Frontend component/integration tests. Current Node tests cover API helpers and pure workflow
  logic, not rendered React interactions.
- Docker image publishing and deployment automation. GitHub Actions CI is implemented, but its
  hosted PostgreSQL job must complete successfully before PostgreSQL behavior is considered
  verified.
- A consistent timezone policy for naive bank statement wall times versus timezone-aware Telegram
  manual transactions and reporting. Duplicate matching currently makes no timezone conversion
  assumption.

## Security Risks and Technical Debt

- Local PostgreSQL `FOR UPDATE`, live Alembic upgrade/downgrade, and PostgreSQL-specific behavior
  remain unverified because no PostgreSQL server is available on this machine. The dedicated CI job
  is intended to verify those paths; SQLite results alone do not verify PostgreSQL locking or
  constraints.
- Duplicate matching is conservative and exact: timestamp, signed amount, currency, normalized
  non-empty description, and instrument label when both sides have one. Changed bank text/time
  formatting can evade detection; no stable bank transaction ID is available in the imported format.
- Preview filter pagination currently fetches matching rows before slicing them in application code;
  large batches may need SQL-level count/offset/limit optimization.
- Imported bank timestamps remain naive local wall times. A product-wide timezone/display policy is
  open.
- Login throttling and expired-session cleanup are absent. The auth migration refuses ambiguous
  normalized-email duplicates; resolve those records before applying it to such a database.
- Backend dependency declarations use open lower bounds and there is no Python lock file. The
  frontend `package-lock.json` is checked in. `pip check` passes, but it does not establish
  dependency freshness. `npm ci` reported five audit advisories (1 low, 1 moderate, 3 high) and
  deprecated Recharts 2.15.4; dependency upgrades are outside this CI slice.
- The backend test client emits one Starlette deprecation warning about its `httpx` integration.
- Vite emits a large-chunk advisory for the ~672 kB minified JavaScript bundle. The build succeeds;
  code splitting is not part of this slice.
- Docker, Docker Compose, and `psql` are not installed on this machine, and localhost port 5432 is
  unreachable. Live PostgreSQL startup/migrations and full-stack/browser import confirmation could
  not be verified locally.
- Production Telegram requires `TELEGRAM_WEBHOOK_SECRET_TOKEN` whenever the bot token is enabled.
  A real Telegram request was not sent.
- Never casually log refresh/link tokens, secrets, transaction descriptions or amounts, imported
  bank rows, Telegram message text, or uploaded statements.

## Local Development Commands

Copy `.env.example` to `.env` and `backend/.env`; configure local PostgreSQL and demo credentials.
For Telegram, set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, and
`TELEGRAM_WEBHOOK_SECRET_TOKEN` as appropriate. Do not configure Telegram with a default Family or
Account ID.

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

# Verification
Set-Location backend
python -m pytest -q
python -m alembic heads
python -m alembic upgrade head --sql

Set-Location frontend
npm test
npm run build
```

To run PostgreSQL integration tests locally, start Compose and create the disposable database once.
These tests truncate every application table, so point both variables at that dedicated test DB:

```powershell
# Repository root; create the database once inside the local Postgres container
docker compose up -d postgres
docker compose exec -T postgres createdb -U family_cash_flow family_cash_flow_integration_test

# Backend; use the host-mapped PostgreSQL port from docker-compose.yml
Set-Location backend
$env:POSTGRES_INTEGRATION_DATABASE_URL = "postgresql+psycopg://family_cash_flow:family_cash_flow_dev@localhost:5433/family_cash_flow_integration_test"
$env:DATABASE_URL = $env:POSTGRES_INTEGRATION_DATABASE_URL
$env:RUN_POSTGRES_INTEGRATION = "1"
$env:POSTGRES_INTEGRATION_REQUIRED = "1"
python -m alembic upgrade head
python -m pytest -m postgres tests/postgres -q
```

The fixture rejects non-PostgreSQL URLs and databases whose names do not end in
`_integration_test`. If the integration flag is off, local collection skips these cases; CI sets the
required flag so a missing database cannot silently pass.

For Telegram, sign into Web, create a Telegram link in Account, then complete `/start <token>` in a
private chat. Use a public HTTPS tunnel for the webhook; see
[Telegram Local Checklist](telegram-local-checklist.md).

## Commands Executed for This Update

Commands were run in Windows PowerShell from the indicated directory:

| Directory | Command | Result |
| --- | --- | --- |
| `backend` | `.venv\Scripts\python.exe -m pytest -q` | **136 passed, 5 skipped, 1 warning in 9.86s.** The five new PostgreSQL cases skipped because this machine has no integration DB. Warning: Starlette deprecation for its `httpx` test-client integration. |
| `backend` | `.venv\Scripts\python.exe -m pytest --collect-only -q` | **141 tests collected in 1.13s** (including five PostgreSQL cases). Same Starlette deprecation warning. |
| `backend` | `.venv\Scripts\python.exe -m pytest -m postgres tests\postgres -q` | **5 skipped, 1 warning.** No local PostgreSQL integration URL was configured. |
| `backend` | `.venv\Scripts\python.exe -m ruff check --select E,F,I tests\postgres\test_postgres_integration.py tests\postgres\conftest.py` | **Passed.** |
| `backend` | `.venv\Scripts\python.exe -m ruff format --check tests\postgres\test_postgres_integration.py tests\postgres\conftest.py` | **Passed; both files formatted.** |
| `backend` | `.venv\Scripts\python.exe -m pip check` | **Passed:** no broken requirements found. |
| `backend` | `.venv\Scripts\python.exe -m alembic heads` | **One head:** `202610050003`. |
| `backend` | `.venv\Scripts\python.exe -m alembic upgrade head --sql` | **Passed:** PostgreSQL offline SQL generated. This did not connect to a database. |
| `frontend` | `$env:NODE_OPTIONS='--use-system-ca'; npm.cmd ci --cache "$env:TEMP\famaly-cash-flow-npm-cache"` | **Passed:** 109 packages installed. npm reported 5 audit advisories (1 low, 1 moderate, 3 high), deprecated Recharts 2.15.4, and an esbuild install-script warning. |
| `frontend` | `npm.cmd test` | **9 passed, 0 failed.** Node built-in test runner. |
| `frontend` | `npm.cmd run build` | **Passed:** TypeScript and Vite; 2,209 modules transformed; JS 672.44 kB (193.00 kB gzip), CSS 17.91 kB. Vite emitted the >500 kB advisory. |
| `backend` | `.venv\Scripts\python.exe -m pytest -m postgres tests\postgres -q` with `POSTGRES_INTEGRATION_REQUIRED=1` and URL unset | **5 setup errors, exit 1, as intended:** verified that the required integration job fails instead of silently skipping. |
| repository root | `& .\backend\.venv\Scripts\python.exe -c "import yaml; p=yaml.load(open('.github/workflows/ci.yml', encoding='utf-8'), Loader=yaml.BaseLoader); assert len(p['jobs']) == 3; print('YAML parsed; jobs:', ', '.join(p['jobs']))"` | **Passed:** `backend-tests`, `postgres-integration`, and `frontend`. This checks YAML syntax, not GitHub Actions execution. |
| repository root | `Get-Command docker,docker-compose,psql -ErrorAction SilentlyContinue`; `Test-NetConnection -ComputerName localhost -Port 5432 -InformationLevel Quiet`; same check on port 5433 | **No Docker/Compose/psql executable; both ports returned False.** |
| repository root | `git diff --check` | **Passed**; Git displayed only its usual LF-to-CRLF working-copy notices. |
| `frontend` | `npm.cmd run dev -- --host 127.0.0.1 --port 4173` and root `Invoke-WebRequest -Uri http://127.0.0.1:4173/ -UseBasicParsing` | Vite started and returned **HTTP 200**. This verifies dev-server startup/static response, not authenticated UI interaction. |

## Recommended Next Slice

Next implement **Everyday Transactions**: build the shared transaction service, authenticated
Family-scoped create/get/update/soft-delete/audit API, and Web manual expense/income plus transaction
management UI. Keep Telegram on the same application/domain services. Do not add budgets or broaden
categorization in that slice.
