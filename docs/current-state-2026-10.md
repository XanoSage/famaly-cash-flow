# Current State: 2026-10-05

The current source-of-truth baseline is `staging` at
`13d87260211b3d2089b0ea7750e295c08f849781`, including Web authentication and Telegram identity/linking.
The Import Review Engine described below is being developed on `codex/import-review-engine` from
that baseline and has not been merged. `main` is unchanged.

## Verified Working Features

- Web email/password authentication uses normalized email, Argon2, short-lived access JWTs, and
  rotating opaque refresh tokens stored as hashes in PostgreSQL. Authenticated APIs derive Family
  from the persisted User.
- Analytics, categories, transactions, imports, and transaction review are family-scoped.
- Telegram identity uses numeric `from.id`; link tokens are random, expire after 15 minutes, are
  stored as SHA-256 hashes, and are consumed atomically. Financial Telegram commands and callbacks
  resolve Family through `TelegramIdentity -> User -> Family` and use shared application services.
- XLSX parsing creates persisted draft previews without persisting Merchant records. Import-review
  applies normalized system/family categorization rules and duplicate checks before returning the
  preview.
- Supported rules are exact normalized merchant, exact normalized bank category, and normalized
  keyword/description. Higher numeric priority wins per output field. Equal-priority contradictory
  outputs add `rule_conflict`; equivalent outputs do not. The idempotent system seed currently maps
  `Супермаркети та продукти` to the system `Еда / Супермаркеты` taxonomy.
- Existing-transaction duplicate matching is Family-scoped and conservative: exact bank timestamp,
  signed amount, currency, and normalized non-empty description must match; payment-instrument
  labels must also match when both are present. Repeated equivalent rows in one upload point to the
  first row number. Confirmed statements re-upload as duplicate candidates.
- Authenticated Family-scoped APIs retrieve/filter previews, patch a row, perform bulk actions,
  optionally apply corrections to matching merchant rows in the current draft, and explicitly save
  a normalized Family merchant rule. Responses include proposed category/subcategory names and IDs,
  review decisions, and Family-safe duplicate summaries.
- Confirmation preserves reviewed category, subcategory, flow, and scope; excludes excluded rows and
  unaccepted duplicates; allows intentionally uncategorized rows; rejects unresolved parse errors;
  and rejects a second confirmation of a confirmed batch.
- A new Alembic migration persists duplicate inclusion, intentional-uncategorized review, review
  timestamp state, and the recomputed `auto_ready_count` / `needs_review_count` batch counters. The
  migration chain remains linear with one head.
- Existing dashboard, transaction review, Web authentication, and Telegram flows remain in place.

## Incomplete Features

- The Web Import Review UI is not implemented. The next slice is upload → preview table → filters →
  row editing → bulk actions → confirm against the APIs described in `docs/import-preview-flow.md`.
- Parse-error source date/amount fields cannot be fixed interactively; users can exclude those rows.
- Draft cleanup/expiration execution is not implemented even though draft expiry metadata exists.
- Only a small supermarket system bank-category mapping is seeded; no broad Ukrainian bank taxonomy
  is intended in this slice.
- Budgets, budget limits, Telegram income entry, Telegram notifications, and a Mini App are not
  implemented.
- The Web client has no full transaction-management pages or frontend test suite. CI and deployment
  automation are absent.
- Imported bank timestamps remain naive local wall times. The duplicate matcher deliberately makes
  no timezone conversion assumption. Telegram manual transaction timestamps are UTC-aware; a
  consistent imported-bank/display timezone policy remains open.

## Security Risks and Limits

- New import endpoints derive Family from the authenticated User. Category/subcategory IDs are
  checked against system/global or caller-Family rows; preview IDs must belong to the target draft.
  Duplicate metadata is loaded only by transaction ID plus caller Family.
- Duplicate matching is intentionally exact to limit false positives. It can miss a real duplicate if
  bank description, local timestamp, or instrument formatting changes. The source XLSX currently has
  no stable bank transaction ID. No tolerance-based match is used.
- PostgreSQL `FOR UPDATE` behavior for draft confirmation/edit serialization and migrations were not
  exercised against a live PostgreSQL server. SQLite tests do not prove PostgreSQL locking behavior.
- Imported bank timestamps have no offset and remain naive; exact duplicate matching uses their
  displayed wall timestamp. This is not a timezone policy for analytics or display.
- Production must set `TELEGRAM_WEBHOOK_SECRET_TOKEN` whenever `TELEGRAM_BOT_TOKEN` is enabled. A
  real production webhook or Telegram Bot API was not exercised.
- Never log link tokens, webhook or bot secrets, Telegram message text, bank rows, transaction
  details, amounts, or uploaded statement contents.
- Login throttling and expired-session cleanup are absent. The auth migration refuses ambiguous
  normalized email duplicates; resolve those rows before upgrading such a database.

## Technical Debt

- Backend dependencies have open lower bounds and no Python lock file. `frontend/package-lock.json`
  is checked in.
- The backend test client emits a Starlette deprecation warning for its httpx integration.
- Repository-wide Ruff findings are not cleaned up by this slice; only changed Python files are
  checked. npm has existing reported audit findings; no broad upgrades were run.
- Vite's built dashboard bundle is above its 500 kB advisory threshold. Bundle splitting is outside
  this slice.
- Docker, docker-compose, and psql are unavailable on this machine, preventing live PostgreSQL
  migration/concurrency checks.

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

## Import Review Verification Results

Commands run on Windows PowerShell from `backend` unless noted:

- `\.venv\Scripts\python.exe -m pytest -q`: **134 passed, 1 warning in 8.79s**. The warning is
  Starlette's deprecated httpx test-client integration. API tests use SQLite.
- `\.venv\Scripts\python.exe -m pytest --collect-only -q`: **134 tests collected in 0.87s**.
- `\.venv\Scripts\python.exe -m pip check`: **No broken requirements found**.
- `\.venv\Scripts\ruff.exe check --select E,F,I <13 changed Python files>`: **passed**.
- `\.venv\Scripts\ruff.exe format --check <13 changed Python files>`: **passed; all 13 already
  formatted**.
- `git diff --check`: **passed**.
- `python -m alembic history --verbose`: **passed**, linear through `202610050003`.
  `python -m alembic heads`: **one head, `202610050003`**.
- `python -m alembic upgrade head --sql`: **passed**, generated offline PostgreSQL SQL through
  `202610050003`. `python -m alembic downgrade 202610050003:202610050002 --sql`: **passed**,
  generated offline downgrade SQL. These are not live migrations.
- `npm.cmd run build` initially failed in `vite:build-html` because Rollup received an emitted
  `index.html` path outside the frontend root. `npm.cmd run build -- --debug` then passed, followed
  by a plain `npm.cmd run build` pass. Both successful builds ran `tsc -b`, transformed 2,199
  modules, and emitted a **618.32 kB** JS bundle (**178.74 kB gzip**). The 500 kB Vite advisory
  remains; the intermittent emitted-path failure is unexplained.
- `Get-Command docker,docker-compose,psql -ErrorAction SilentlyContinue` found none on PATH. No live
  PostgreSQL migration/concurrency test or real Telegram Bot API smoke test ran.

## Recommended Next Slice

Build the Web Import Review UI against the stable backend contract: XLSX upload, paginated/filterable
preview, row editing, merchant-wide and selected-row bulk actions, explicit duplicate/uncategorized
decisions, and confirmation. Keep review business logic in backend services.
