# Current State (2026-10-05)

The source-of-truth branch is `staging`, at `bcb698bfa01ac79e16fe93f333496e6eb5f40305` for this
work. This feature branch, `codex/web-import-review-ui`, was created from that staging commit.
`main` was not changed. This document describes the implementation-plan audit and the verified
Web Import Review and accounts work on the feature branch.

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
- `AGENTS.md` contains the repository's development constraints and read-before-edit documentation
  list.

## Implementation Plan Status

| Phase | Status | Verified state |
| --- | --- | --- |
| 0. Repo and branch setup | Complete | `main`, `staging`, and feature-branch workflow exist. This task branched from `staging`; no merge to `main`. |
| 1. Monorepo skeleton | Complete | Backend, frontend, infra, and docs are present. |
| 2. Backend skeleton | Complete | FastAPI app, health route, and pytest suite exist. |
| 3. Database and migrations | Implemented; live DB check blocked | PostgreSQL Compose config, SQLAlchemy models, seeds, and a linear Alembic chain exist. Offline SQL generation passes; no PostgreSQL server is available locally for an actual upgrade. |
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
| 15. DevOps MVP | Partial | Local Compose and a backend Dockerfile exist. GitHub Actions CI and a verified deployment path are absent. |

## Incomplete Features

- Budget creation/limits, budget notifications, Telegram notifications, Telegram income-entry flow,
  and a Telegram Mini App.
- Full categorization breadth, transaction create/delete/audit APIs, and complete everyday Web
  transaction-management screens.
- Parse-error date/amount correction; currently users can exclude invalid rows.
- Draft-expiration cleanup execution. Draft expiry metadata exists.
- Frontend component/integration tests. Current Node tests cover API helpers and pure workflow
  logic, not rendered React interactions.
- CI workflows and deployment automation.
- A consistent timezone policy for naive bank statement wall times versus timezone-aware Telegram
  manual transactions and reporting. Duplicate matching currently makes no timezone conversion
  assumption.

## Security Risks and Technical Debt

- PostgreSQL `FOR UPDATE`, live Alembic upgrade/downgrade, and PostgreSQL-specific behavior were not
  exercised here. SQLite tests do not verify PostgreSQL locking or constraints.
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
  frontend `package-lock.json` is checked in. `pip check` passes in the current local environment;
  dependency freshness was not established by that check.
- The backend test client emits one Starlette deprecation warning about its `httpx` integration.
- Vite emits a large-chunk advisory for the ~672 kB minified JavaScript bundle. The build succeeds;
  code splitting is not part of this slice.
- Docker, Docker Compose, and `psql` are not installed on this machine, and localhost port 5432 is
  unreachable. Live database startup, migrations, and a full-stack/browser import confirmation could
  not be verified.
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

For Telegram, sign into Web, create a Telegram link in Account, then complete `/start <token>` in a
private chat. Use a public HTTPS tunnel for the webhook; see
[Telegram Local Checklist](telegram-local-checklist.md).

## Commands Executed for This Update

Commands were run in Windows PowerShell from the indicated directory:

| Directory | Command | Result |
| --- | --- | --- |
| `backend` | `.venv\Scripts\python.exe -m pytest -q` | **136 passed, 1 warning in 9.11s**. Warning: Starlette deprecation for `httpx` test-client integration. |
| `backend` | `.venv\Scripts\python.exe -m pytest --collect-only -q` | **136 tests collected in 1.20s.** |
| `backend` | `.venv\Scripts\python.exe -m pip check` | **No broken requirements found.** |
| `backend` | `.venv\Scripts\python.exe -m alembic heads` | **One head:** `202610050003`. |
| `backend` | `.venv\Scripts\python.exe -m alembic history --verbose` | **Passed**, linear history through `202610050003`. |
| `backend` | `.venv\Scripts\python.exe -m alembic upgrade head --sql` | **Passed**, PostgreSQL offline SQL generated through the single head; this did not connect to a database. |
| `backend` | `.venv\Scripts\python.exe -m ruff check app\api\router.py app\api\routes\accounts.py app\schemas\accounts.py tests\test_accounts_api.py` | **Passed** after formatting the new account import and using annotated FastAPI dependencies. |
| `backend` | `.venv\Scripts\python.exe -m ruff format --check app\api\router.py app\api\routes\accounts.py app\schemas\accounts.py tests\test_accounts_api.py` | **Passed; all 4 files formatted.** |
| `frontend` | `npm.cmd test` | **9 passed, 0 failed.** Uses Node's built-in test runner; no new test dependencies were installed. |
| `frontend` | `npm.cmd run build` | **Passed** TypeScript and Vite; 2,209 modules transformed; JS 672.44 kB (193.00 kB gzip), CSS 17.91 kB. Vite emitted the >500 kB advisory. |
| repository root | `git diff --check` | **Passed**; Git displayed only its usual LF-to-CRLF working-copy notices. |
| `frontend` | `npm.cmd run dev -- --host 127.0.0.1 --port 4173` and root `Invoke-WebRequest -Uri http://127.0.0.1:4173/ -UseBasicParsing` | Vite started and returned **HTTP 200**. This verifies dev-server startup/static response, not authenticated UI interaction. |
| repository root | `Get-Command docker,docker-compose,psql -ErrorAction SilentlyContinue` | No executable found. |
| repository root | `Test-NetConnection -ComputerName localhost -Port 5432 -InformationLevel Quiet` | **False**; no local PostgreSQL listener. |

## Recommended Next Slice

Complete the everyday transaction workflow: add authenticated Family-scoped transaction create,
get, soft-delete, and audit behavior with Decimal-safe service tests, then build the Web transaction
management/manual-entry UI on those shared services. Keep Telegram on the same domain services.
Afterward, add CI for backend tests, frontend tests/build, and migration-head checks.
