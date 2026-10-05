# Current State: 2026-10-05

This document records the implementation state after the rebaseline and Web identity/authorization
slice on `codex/identity-auth-foundation`. The rebaseline audit was committed as `0f5aae8` and merged
into `staging` at `843c76f`. No work from this slice has been merged to `main`.

## Verified Working Features

- FastAPI health endpoint, family-scoped analytics, category listing, transaction listing/limited
  updates, XLSX draft preview/reopen/confirmation, and the existing Telegram webhook remain present.
- Web login uses normalized email and Argon2 password hashes. Access JWTs expire after the configured
  15 minutes, identify the user UUID in `sub`, and carry no trusted family claim.
- Refresh sessions persist in PostgreSQL through `auth_sessions`. Only SHA-256 refresh-token hashes
  are stored; opaque refresh tokens rotate and are revoked on logout. The raw token is delivered as
  an HttpOnly cookie.
- `GET /api/v1/auth/me` returns user ID, display name, email, language, family ID, and family name.
- Analytics, categories, transactions, and imports require a current authenticated user. Web routes
  derive family scope from the persisted user's family. Account, category, merchant, transaction,
  and import IDs are checked against that family. Import creation derives the uploader from the
  authenticated user. Spoofed `family_id` and uploader query parameters do not change the scope.
- The frontend has a login form, bootstraps access through the refresh cookie, keeps the access JWT
  in memory, calls `/auth/me`, sends bearer tokens through a reusable API client, and has no manual
  Family ID field. The existing dashboard remains intact.
- Local demo seed creates/updates a demo user from `DEMO_USER_EMAIL` and `DEMO_USER_PASSWORD` and
  stores an Argon2 hash. No demo password is committed or printed.
- Three Alembic revisions form one linear chain. PostgreSQL offline SQL generation succeeds.

## Architecture

```text
Web user -> authenticated FastAPI request -> persisted User -> User.family
         -> shared application/domain services -> PostgreSQL

Telegram user -> TelegramIdentity -> application User -> User.family
               -> same shared application/domain services -> PostgreSQL
```

The second path is the next slice; `TelegramIdentity` and account linking are not implemented here.
Telegram still uses `TELEGRAM_DEFAULT_FAMILY_ID` and `TELEGRAM_DEFAULT_ACCOUNT_ID`.

## Implementation Plan Phase Audit

| Phase | State | Current evidence |
|---|---|---|
| 0. Repo and branch setup | Complete | `staging` contains the rebaseline; feature work starts from it. |
| 1. Monorepo skeleton | Complete | Backend, frontend, infrastructure, and docs are present. |
| 2. Backend skeleton | Complete | FastAPI health route and backend tests pass. |
| 3. Database and migrations | Partial | PostgreSQL models, Compose config, category seed, and three revisions exist. Live PostgreSQL migration was unavailable here. Budget, notification, audit-log, and Telegram identity tables are absent. |
| 4. Auth MVP | Complete | Login, Argon2, short-lived JWT, persistent rotating refresh sessions, logout, `/me`, and family-derived authorization are implemented and tested. |
| 5. XLSX parser spike | Partial | Parser and synthetic XLSX tests exist; imported timestamps remain naive and the timezone contract is unsettled. |
| 6. Import preview backend | Partial | Upload, persisted draft, preview retrieval, and expiry metadata exist. Duplicate detection, expiry cleanup, row editing, and bulk actions are missing. |
| 7. Categorization engine | Not started | Rule model/table exists, but no rule engine or rule CRUD is wired. |
| 8. Import confirmation | Partial | Confirmation creates transactions and validates batch/account family. Preview editing, bulk actions, and active duplicate marking are missing. |
| 9. Transactions API | Partial | List/filter and limited PATCH are present. Detail/create/delete endpoints, soft-delete action, and audit history are absent. |
| 10. Analytics API | Partial | Summary, dashboard, category, merchant, timeline, savings, insights, and Work/FOP APIs exist. Budgets are absent. |
| 11. Frontend skeleton | Partial | Login and authenticated dashboard loading work in the implementation; router and planned app shell/pages are absent. |
| 12. Import UI | Not started | No upload, preview editing, bulk action, or confirmation UI exists. |
| 13. Operations and dashboard UI | Partial | Dashboard and recent review actions exist; full transaction and cash-entry flows are absent. |
| 14. Budgets and notifications | Not started | No models, migrations, APIs, or UI exist. |
| 15. DevOps MVP | Partial | Dockerfiles/Compose and build config exist; CI and deployment automation are absent. Docker was unavailable for local checks. |

## Incomplete Features and Technical Debt

- **Telegram authorization:** there is no persistent Telegram-user-to-application-user mapping or
  per-user authorization. Default family/account routing remains a security risk if the webhook is
  exposed. Telegram write handlers still contain persistence logic instead of consistently using
  shared services.
- **Import and categorization:** preview rows cannot be edited through the API; bulk actions,
  merchant/category rules, duplicate comparison, conflict handling, and draft cleanup are missing.
- **Transactions and audit:** PATCH changes category, comment, and review state. Soft-delete fields
  exist but no endpoint uses them. There is no audit log.
- **Budgets:** budget and notification concepts remain documentation-only.
- **Frontend:** one dashboard and login screen exist. There is no router, import UI, full operations
  UI, or frontend test suite.
- **Timezones:** bank XLSX parsing produces naive datetimes; Telegram manual input uses naive
  `datetime.now()`. PostgreSQL timestamp behavior was not verified.
- **Session operations:** there is no expired-session cleanup job or login throttling. Revoked and
  expired rows remain in the auth-session table until future cleanup is added.
- **Migration data check:** the new migration normalizes existing emails and requires them to be
  globally unique. It intentionally aborts if legacy rows collide after trim/lowercase; resolve
  those identities before applying the migration to such a database.
- **Dependency reproducibility:** backend requirements have open lower bounds and no Python lock
  file. `frontend/package-lock.json` is present. The backend test client emits a Starlette warning
  that its httpx integration is deprecated.
- **Frontend dependencies:** the baseline `npm audit` reported five fix-available findings (3 high,
  1 moderate, 1 low); no broad dependency upgrades were made for authentication. Vite also warns
  that the existing minified dashboard chunk exceeds 500 kB.
- **Docs/product scope:** `mvp-scope.md` still calls Telegram “Later”, although Telegram is a core
  product requirement. Reconcile that wording in a product-doc task.

## Security Notes

- Web financial endpoints now require an active user and live server-side session. The backend
  derives family access from persisted user data; UUIDs in query strings cannot switch families.
- Email is globally unique for the one-family-per-user MVP. The login lookup and migration both
  trim and lowercase email addresses.
- Production settings reject the local JWT placeholder, JWT secrets shorter than 32 characters,
  insecure production cookies, and `SameSite=None` without Secure.
- Use a same-site custom domain for frontend/API in production. If cross-site cookies are required,
  configure `AUTH_COOKIE_SAMESITE=none`, `AUTH_COOKIE_SECURE=true`, HTTPS, and credentialed CORS for
  the exact frontend origin. Browsers may block third-party cookies.
- Do not log JWTs, refresh tokens, password hashes, transaction details, bank rows, amounts, or
  Telegram message text. Upload size limits are still absent.

## Local Development

Create a local `.env` from `.env.example`, set `DEMO_USER_EMAIL` and `DEMO_USER_PASSWORD`, and keep
the file untracked. For direct backend execution, place a copy at `backend/.env` because settings
load `.env` from the working directory.

```powershell
# Repository root: start PostgreSQL
docker compose up -d postgres

# Backend: migrate, seed, and start API
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
```

Open `http://localhost:5173/` and log in with the local demo email/password. Use `localhost` for
both frontend and API so the refresh cookie remains same-site. Backend tests run with
`python -m pytest`; frontend TypeScript and production build run with `npm run build`.

## Verification Results

The backend API tests use SQLite. SQLite does not establish PostgreSQL migration, row-locking, or
timestamp behavior.

- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`: **121 passed, 1 warning in 12.14s**.
  The warning is Starlette's deprecated `httpx` test-client integration.
- `cd backend; .\.venv\Scripts\python.exe -m pip check`: **No broken requirements found.**
- `cd backend; .\.venv\Scripts\ruff.exe check --select F,I <changed Python files>` and
  `ruff.exe format --check <changed Python files>`: **passed**; 30 changed Python files are
  formatted. The repository-wide `ruff check app tests --statistics --output-format concise` check
  is not clean: it reports 240 findings, mainly datetime calls without timezone, FastAPI
  `Depends`/`Query` default calls, quoted annotations, and import ordering. No broad cleanup was
  included in this slice.
- `cd backend; .\.venv\Scripts\python.exe -m alembic history --verbose`: **passed**; the auth
  revision `202610050001` is head after `202605120002` and `202605120001`.
- `cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head --sql`: **passed** and generated
  PostgreSQL SQL including the email collision guard, unique constraint, and `auth_sessions` table.
  It was offline SQL generation, not a live database migration.
- `cd frontend; npm.cmd ci --cache <temporary npm cache> --prefer-offline`: **passed**, 109 packages
  installed. npm reported five audit findings (1 low, 1 moderate, 3 high); Recharts is deprecated,
  and npm printed an esbuild install-script warning.
- `cd frontend; npm.cmd run build`: **passed** (`tsc -b` and Vite). The minified JavaScript bundle is
  612.47 kB (177.39 kB gzip), above Vite's 500 kB warning threshold.
- Browser smoke check with a temporary SQLite database, FastAPI at `localhost:8000`, and Vite at
  `localhost:5173`: **passed**. Login loaded the authenticated demo family dashboard and seeded
  transactions; logout returned to the login screen. This did not exercise PostgreSQL.
- Docker Compose and live PostgreSQL checks were unavailable: `docker` and `psql` were not installed
  or on `PATH`. The Compose startup, live migration, and PostgreSQL-backed seed/login remain
  unverified.

## Recommended Next Slice

Implement **TelegramIdentity + secure one-time Telegram account linking + removal of
`TELEGRAM_DEFAULT_FAMILY_ID` / `TELEGRAM_DEFAULT_ACCOUNT_ID`**. Link Telegram to the existing
application `User`, resolve the family through that persisted identity, authorize commands and
callbacks, and route shared writes through the same application/domain services used by Web. Add
tests for one-time/expired/replayed links, unlinked users, cross-family denial, and authorized
Telegram callbacks. Do not create a second auth/session system for Telegram.
