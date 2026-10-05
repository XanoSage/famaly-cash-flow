# Current State: 2026-10-05

This audit was performed on `codex/rebaseline-2026-10`, created from
`origin/staging` at `191428b50f948e92b740c86f3f03bb3f540033a2`. No changes were made to
`main`, and no product code was changed during the audit.

## Verified Working Features

- FastAPI starts locally and `GET /api/v1/health` returns `{"status":"ok"}`.
- The XLSX importer parses the configured bank format, stores draft previews, reopens drafts, and
  confirms rows into transactions. These paths have backend tests using in-memory SQLite.
- Transaction listing and limited updates, system category listing, and the analytics APIs are
  implemented. Analytics include summary, dashboard, category, merchant, daily timeline, savings,
  insights, and Work/FOP views. Backend amounts and aggregates use `Decimal`/PostgreSQL `NUMERIC`.
- The Telegram webhook supports `/start`, `/summary`, `/review`, `/done`, review callbacks for
  marking and categorizing transactions, and simple manual expense text. Summary reuses the
  analytics service; other Telegram writes still contain their own persistence logic.
- The frontend is a single React dashboard with date/scope filters, RU/UK labels, summary charts,
  recent transactions, and review actions. The Vite dev server serves the app shell.
- Two Alembic revisions form a single linear chain and generate PostgreSQL SQL in offline mode.

## Implementation Plan Phase Audit

| Phase | State | Verified implementation |
|---|---|---|
| 0. Repo and branch setup | Complete | `main` and `staging` exist; feature work is integrated on `staging`. |
| 1. Monorepo skeleton | Complete | `backend`, `frontend`, `infra`, and `docs` exist. |
| 2. Backend skeleton | Complete | FastAPI app, health route, project structure, and tests exist. |
| 3. Database and migrations | Partial | PostgreSQL Compose service, SQLAlchemy models, two Alembic revisions, and category seed exist. A live PostgreSQL migration was not verifiable on this machine. Budget, notification, audit-log, and Telegram identity tables are absent. |
| 4. Auth MVP | Not started | User/password-hash model fields and JWT settings exist, but there are no auth routes, token/session implementation, password handling, or current-user dependency. |
| 5. XLSX parser spike | Partial | Parser and synthetic XLSX tests exist. Bank and Telegram transaction timestamps are naive; timezone conversion is not defined. |
| 6. Import preview backend | Partial | Upload, persisted draft, preview retrieval, and expiry metadata exist. Duplicate detection, cleanup of expired drafts, row editing, and bulk actions do not. |
| 7. Categorization engine | Not started | `categorization_rules` model/table exists, but no rule engine or rule CRUD is wired. The parser has only hard-coded flow/scope/review heuristics and does not assign categories. |
| 8. Import confirmation | Partial | Confirmation creates transactions and skips rows already marked excluded/duplicate. There is no preview editing/action API, and the importer does not mark duplicate candidates. |
| 9. Transactions API | Partial | List/filter and limited PATCH are present. Detail/create/delete endpoints, soft-delete action, audit history, and several planned filters are absent. |
| 10. Analytics API | Partial | Summary, dashboard, category, merchant, daily timeline, savings, insights, and Work/FOP APIs exist. Budgets and budget-risk reporting do not. |
| 11. Frontend skeleton | Partial | React/Vite/TypeScript and a dashboard screen exist. Routing, app shell, login, and authenticated API access do not. |
| 12. Import UI | Not started | No upload, preview editing, bulk action, or confirmation UI exists. |
| 13. Operations and dashboard UI | Partial | Dashboard and recent review queue exist. Full transactions screen, Web manual/cash entry, and planned dashboard blocks are absent. |
| 14. Budgets and notifications | Not started | No budget/notification models, migrations, APIs, or UI exist. |
| 15. DevOps MVP | Partial | Backend Dockerfile, Compose, and frontend build configuration exist. CI workflows and deployment automation are absent; Docker checks could not run here. |

## Incomplete Features and Technical Debt

- **Identity and tenant isolation:** API routes accept `family_id` directly. There is no
  authentication, authorization dependency, or verified ownership context. Treat every
  family-scoped Web endpoint as unsafe to expose outside local development.
- **Telegram identity:** runtime routing uses `TELEGRAM_DEFAULT_FAMILY_ID` and
  `TELEGRAM_DEFAULT_ACCOUNT_ID`. There is no persistent Telegram-user-to-application-user mapping
  or per-user authorization. The webhook secret is optional, so an unset secret leaves the
  endpoint without request authentication.
- **Duplicate detection:** the parser computes a fallback key in `normalized_payload`, but does not
  compare it with other rows or stored transactions. No row receives `duplicate_candidate` from
  the current import path; the confirmation service's duplicate skip is therefore not an active
  safeguard.
- **Import and categorization:** preview rows cannot be edited through the API, and bulk actions,
  merchant/category rules, and categorization conflict handling are missing. `expires_at` is set,
  but no scheduled cleanup is present.
- **Transactions and audit:** PATCH changes only category, comment, and `needs_review`. Soft-delete
  fields exist but no delete route sets them. There is no `AuditLog` model or migration.
- **Budgets:** budget and notification concepts appear in planning documents, but there are no
  implementation models, migrations, routes, or screens.
- **Frontend:** one dashboard component reads a manually supplied family UUID from browser storage.
  There is no router, auth flow, import UI, full operations UI, or frontend test script/suite.
- **Timezones:** bank XLSX parsing produces naive datetimes, Telegram manual input uses
  `datetime.now()` without a timezone, and the database columns are timezone-aware. PostgreSQL
  session/server timezone behavior has not been verified. The test suite uses SQLite and does not
  establish production timestamp behavior.
- **Dependency reproducibility:** `backend/pyproject.toml` uses open lower bounds and has no Python
  lock file. `frontend/package-lock.json` exists and `npm ci` succeeded. A clean Python install
  resolved FastAPI 0.142.2, SQLAlchemy 2.1.3, pytest 9.1.1, Starlette 1.7.0, and httpx 0.28.1;
  pytest emitted one Starlette deprecation warning about its httpx test client integration.
  `pip list --outdated --format=json` reported pip 25.0.1 (latest 26.2.1) and pydantic-core 2.46.5
  (latest 2.49.0); the installed Pydantic release pins pydantic-core to 2.46.5, so update them as
  a compatible pair rather than upgrading the core package alone.
- **Frontend dependency health:** on 2026-10-05, `npm outdated --json` reported newer versions for
  React/React DOM 19.2.7 (wanted 19.3.0), Vite 7.3.5 (wanted 7.3.6; latest 8.3.2), TypeScript
  5.9.3 (latest 7.0.2), `@vitejs/plugin-react` 5.2.0 (latest 6.1.2), `lucide-react` 0.468.0
  (latest 1.52.0), Recharts 2.15.4 (latest 3.10.1), and the React type packages. npm reported
  Recharts 2.x is no longer an active branch. `npm audit` reported 5 fix-available vulnerabilities:
  3 high, 1 moderate, and 1 low across Browserslist, Nano ID, PostCSS, esbuild, and
  baseline-browser-mapping. No dependency upgrades were made in this audit.
- **Build warning:** Vite emitted a 609.31 kB minified JavaScript chunk warning (over its 500 kB
  guidance threshold). The build still succeeded.
- **Local docs and startup:** `frontend/README.md` contains old absolute Windows paths. Compose
  starts Postgres and the API, but does not apply migrations or seed data; those remain manual
  steps documented under `backend/README.md`. `mvp-scope.md` still lists Telegram outside the MVP
  and `roadmap.md` labels it later; reconcile those statements with Telegram's core product role.

## Security Risks

- Without authentication, a caller who supplies a known family UUID can read family analytics and
  transactions or update transactions through the API. UUIDs are identifiers, not authorization.
- Telegram commands and callbacks act on the configured default family/account rather than an
  authenticated mapped user. Keep the bot local until identity mapping and authorization exist.
- `docker-compose.yml` and `.env.example` contain development credentials and a placeholder JWT
  secret. They must not be used as production credentials.
- Uploads have an extension check and are deleted after parsing, but no request/file-size limit is
  defined. Do not add logs containing financial rows, descriptions, amounts, or Telegram message
  text.

## Local Development Commands

Run Compose from the repository root; run Python commands from `backend`.

```powershell
# Backend environment (Python 3.11+)
cd backend
python -m pip install -e ".[dev]"
cd ..
docker compose up -d postgres
cd backend
alembic upgrade head
python -m app.db.seed_system_categories
python -m app.db.seed_demo_dashboard
uvicorn app.main:app --reload
python -m pytest
```

```powershell
# Frontend
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
npm run build
```

Frontend defaults to `http://localhost:8000/api/v1`; override with
`VITE_API_BASE_URL` when needed. On the audit machine, `python` was not on `PATH`, and npm needed
`NODE_OPTIONS=--use-system-ca` plus a temporary cache to work around the local certificate/cache
setup. These are machine setup details, not repository code fixes.

## Commands Executed and Results

Environment: Windows PowerShell, Python 3.12.14, Node 24.21.0, npm 11.19.0.

| Command/check | Result |
|---|---|
| From backend: .\.venv\Scripts\python.exe -m pip list --outdated --format=json with PIP_CACHE_DIR set to $env:TEMP\family-cash-flow-pip-cache | Exit 0; pip and pydantic-core updates were reported as described above. |
| `python -m pytest` from `backend` | Could not start: `python` was not on `PATH`. |
| From `backend`: `.\.venv\Scripts\python.exe -m pip install -e '.[dev]' --use-feature=truststore --timeout 20 --retries 0` with `PIP_CACHE_DIR` set to `$env:TEMP\family-cash-flow-pip-cache` | Exit 0; resolved unpinned package versions listed above. `pip check` reported no broken requirements. |
| From `backend`: `.\.venv\Scripts\python.exe -m pytest` | Exit 0: **106 passed, 1 warning, 23.71 s**. Tests use in-memory SQLite, not PostgreSQL. |
| `npm.cmd run build` before install | Could not start: `tsc` was missing because `node_modules` was absent. |
| From `frontend`: set `$env:NODE_OPTIONS='--use-system-ca'`, set `$npmCache = Join-Path $env:TEMP 'family-cash-flow-npm-cache'`, then run `npm.cmd ci --cache $npmCache --prefer-offline` | Exit 0; 109 packages installed. npm printed a Recharts deprecation notice and reported 5 vulnerabilities. |
| `npm.cmd run build` from `frontend` | Exit 0; `tsc -b` and Vite production build passed. Vite reported the 609.31 kB chunk warning. |
| `npm.cmd audit --json` | Exit 1 because of 5 fix-available findings: 3 high, 1 moderate, 1 low. |
| `npm.cmd outdated --json` | Exit 1 because newer package versions are available. See dependency notes above. |
| From `backend`: `.\.venv\Scripts\python.exe -m alembic history --verbose` | Exit 0; one head, `202605120002`, after `202605120001`. |
| From `backend`: `.\.venv\Scripts\python.exe -m alembic upgrade head --sql` | Exit 0; generated 11,330 bytes of PostgreSQL SQL for both revisions. This is offline generation, not a live database migration. |
| From `backend`: `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`, then GET `/api/v1/health` | Server started; HTTP 200 with `{"status":"ok"}`. |
| From `frontend`: `npm.cmd run dev -- --host 127.0.0.1 --port 5173`, then GET `/` | Server started; HTTP 200 with `text/html`. |
| `docker --version`, `docker compose version`, `docker compose config --quiet`, `docker compose ps -a` | Each was blocked with exit 1: `docker` is not recognized. No PostgreSQL Windows service, `psql`/`postgres` command, or listener on port 5433 was found. |
| `git diff --check` | Exit 0; Git printed a working-copy LF-to-CRLF notice for `README.md`. |

The actual `alembic upgrade head` against PostgreSQL, Compose startup, demo seeding against
PostgreSQL, and database-backed local flows remain unverified on this machine.

## Recommended Next Implementation Slices

1. **Next task — Identity/Authorization foundation for Web and Telegram.** Add email/password
   authentication and `/auth/me`; derive family context from the authenticated user instead of
   trusting `family_id`; add an Alembic-backed Telegram identity link with a secure, one-time linking
   flow; authorize Telegram commands/callbacks as the linked application user; remove the default
   family/account routing shortcut; route both channels through shared application/domain services.
   Add tests for login, link lifecycle, cross-family denial, and Telegram callback authorization.
2. Implement duplicate detection, preview row editing/bulk actions, and the categorized-rule engine
   as separately testable backend slices. Set an explicit timezone contract for imported and manual
   transactions before enabling real data.
3. Build the Web import/review and full transactions flows on the secured APIs; add frontend tests.
4. Add budgets/notifications and CI checks after their data/API contracts are implemented.
