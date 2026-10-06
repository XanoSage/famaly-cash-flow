# Testing

## Подход MVP

Backend:

- unit tests;
- integration tests с тестовой базой;
- ручная проверка API через Swagger/OpenAPI.

Frontend:

- Node tests for frontend API requests and pure helpers;
- Playwright browser-to-PostgreSQL coverage for the core Web journey.

## Test Data

- Системные категории seed-ятся обязательно.
- Demo transactions нужны для frontend/dev.
- В репозитории можно хранить synthetic sample.
- Реальные sanitized XLSX-файлы не хранятся в Git.

## PostgreSQL integration tests

The default `python -m pytest -q` suite uses its existing SQLite fixtures and skips the tests under
`backend/tests/postgres` unless explicitly enabled. These tests use a real PostgreSQL database and
cover refresh-token rotation/concurrency, Telegram link-token consumption/concurrency/rollback,
import review/confirmation and Decimal persistence, transaction create/update/delete audit persistence
with soft-delete retention, and PostgreSQL unique/FK constraints.
The Cash Ledger integration case additionally verifies the active-wallet uniqueness path, linked
withdrawal Decimal persistence, paired audit records, and paired soft deletion against PostgreSQL.

The PostgreSQL fixture requires all of the following:

- `RUN_POSTGRES_INTEGRATION=1`;
- `POSTGRES_INTEGRATION_DATABASE_URL` with a PostgreSQL driver;
- a database name ending in `_integration_test`;
- exactly one Alembic head, with the database already migrated to that head.

Each test truncates application tables in that database. Use a disposable test database only; never
point this URL at development, staging, or production data. CI sets `POSTGRES_INTEGRATION_REQUIRED=1`
so missing connection settings fail the job instead of silently skipping the integration tests.
GitHub Actions provisions PostgreSQL 18.6, upgrades the live database, downgrades the newest
revision and upgrades it again, then runs the marked integration suite. See
[`current-state-2026-10.md`](current-state-2026-10.md) for local commands and the verified run
results.

## Web transaction helpers

Node tests cover authenticated transaction list/create/update/delete requests, date and pagination
filters, browser-local timestamp conversion to offset-aware ISO timestamps, and exact formatting of
Decimal amount strings without converting money to floating point. They also cover Cash Ledger API
request paths and string-valued Decimal payloads.

## Full-stack browser E2E

The `fullstack-e2e` GitHub Actions job uses Playwright with Chromium, the built Vite production bundle,
a running FastAPI process, and a fresh PostgreSQL 18.6 service. It runs `alembic upgrade head` from an
empty database, seeds the system categories and the isolated `example.test` E2E family, then starts
the API and Vite preview. Playwright's bounded `webServer` URL probes wait for both HTTP endpoints;
no credentials are added to browser storage and the refresh token remains HttpOnly.

The single sequential browser journey covers login and refresh after page reload, XLSX upload and
persisted review, same-file duplicate detection, category correction with a future merchant rule,
confirmation and imported dashboard totals, manual expense/income, edit and soft delete analytics,
cash wallet setup, a card-to-cash withdrawal without expense double counting, a cash expense, RU/UK
navigation labels, and a mobile viewport smoke check. Its only statement is synthetic and committed
under `frontend/e2e/fixtures/`. The seed command is opt-in (`python -m app.db.seed_e2e`) and is not
part of normal startup.

Local browser run, after PostgreSQL has been migrated and both E2E variables are set:

```powershell
Set-Location backend
$env:APP_ENV = "test"
$env:DATABASE_URL = "postgresql+psycopg://family_cash_flow:family_cash_flow_e2e_test_only@localhost:5432/family_cash_flow_e2e"
$env:E2E_TEST_EMAIL = "e2e-owner@example.test"
$env:E2E_TEST_PASSWORD = "e2e-only-password-not-for-real-users"
python -m alembic upgrade head
python -m app.db.seed_system_categories
python -m app.db.seed_e2e

Set-Location ..\frontend
$env:VITE_API_BASE_URL = "http://localhost:8000/api/v1"
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
```

Run this only against a disposable E2E database. Playwright diagnostics include only API status,
method, and sanitized route; browser screenshots/traces are retained only on failure and contain
synthetic E2E data. For private bank data validation, use the separate
[Real Data Smoke Checklist](real-data-smoke-checklist.md); never put a real statement in the E2E
fixture or CI.

## Что тестировать в первую очередь

### XLSX parser

- чтение файла;
- распознавание колонок;
- нормализация даты;
- нормализация суммы;
- извлечение описания и продавца.

### Categorization

- keyword rules;
- merchant rules;
- ручные правила;
- неизвестные операции.

### Duplicates

- дубль по bank transaction id;
- дубль по дата + сумма + описание;
- недубли при похожих операциях.

### Analytics

- суммы по категориям;
- суммы по продавцам;
- динамика по дням;
- средний расход в день.

### Auth

- логин;
- refresh token;
- доступ к данным только своей семьи.

## Цель тестов

Тесты нужны не для формальности, а чтобы самые важные финансовые расчеты не ломались при изменениях.
