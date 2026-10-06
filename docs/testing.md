# Testing

## Подход MVP

Backend:

- unit tests;
- integration tests с тестовой базой;
- ручная проверка API через Swagger/OpenAPI.

Frontend:

- ручная проверка в MVP;
- Playwright позже, когда интерфейс стабилизируется.

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
Decimal amount strings without converting money to floating point. There is no React rendering or
browser-to-PostgreSQL test harness yet.

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
