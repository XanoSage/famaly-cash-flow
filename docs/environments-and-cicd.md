# Environments And CI/CD

## Environments

### Local

Используется для разработки.

- Docker Compose.
- Локальный PostgreSQL.
- Можно использовать реальные данные только осознанно и без коммита файлов.

### Staging

Используется для проверки деплоя и интеграции.

- Backend: Cloud Run staging service.
- Frontend: Firebase Hosting staging channel/project.
- Database: staging Cloud SQL или отдельная staging schema.
- Данные: обезличенная копия выписки.

### Production

Используется для реальной семейной аналитики.

- Backend: Cloud Run production service.
- Frontend: Firebase Hosting production.
- Database: production Cloud SQL.
- Данные: реальные финансовые данные.

## Staging Data Policy

На staging используем обезличенную копию выписки. Структура, типы операций, категории и характерные суммы могут сохраняться, но чувствительные данные должны быть очищены или замаскированы.

## CI/CD MVP

The check-only workflow is `.github/workflows/ci.yml`. It runs on pushes and pull requests targeting
`staging`, `feature/**`, and `codex/**` and has four jobs:

- backend fast tests using the existing SQLite fixtures, dependency consistency, and Ruff checks on
  changed Python files only (`E`, `F`, `I` plus format check);
- PostgreSQL 18.6 integration tests against a dedicated disposable database, with a real Alembic
  upgrade, newest-revision downgrade/upgrade, and tests for auth refresh, Telegram identity linking,
  import confirmation/Decimal persistence, and PostgreSQL constraints;
- locked frontend install (`npm ci`), frontend tests, and TypeScript/Vite production build.
- full-stack browser E2E using Playwright/Chromium, the production Vite preview, FastAPI, and a fresh
  PostgreSQL 18.6 service. It migrates an empty database with Alembic, seeds synthetic test-only
  categories/family/account data, and runs the user journey through HTTP. It does not require
  Telegram credentials.

The PostgreSQL job waits for the service health check and a `pg_isready` probe. It requires its
integration flag and database URL. Its test fixture verifies a
database name ending in `_integration_test`, and truncates application data before each test. Do not
use a local development or shared database for this suite. The workflow does not publish images or
deploy to Cloud Run/Firebase; those remain separate DevOps work.

The recommended required branch checks after reviewing branch protection are `backend-tests`,
`postgres-integration`, `frontend`, and `fullstack-e2e`. This repository change does not alter GitHub
branch protection settings.

The E2E frontend and API use `http://localhost` on separate ports, which remains same-site for the
HttpOnly refresh cookie. CI sets `AUTH_COOKIE_SECURE=false`, `SameSite=Lax`, and an exact credentialed
CORS origin only for the test server process. Production cookie defaults are unchanged. Playwright
starts both local servers and polls their health URLs with bounded timeouts; the frontend is served
from the production build rather than Vite's development server. Failure-only browser diagnostics
are uploaded as a short-retention Actions artifact.

The initial PostgreSQL integration workflow run [37363137308](https://github.com/XanoSage/famaly-cash-flow/actions/runs/37363137308)
passed all three then-existing jobs on commit `d44217831d37df67e0ecc64df800046b507ca07c`, including
PostgreSQL 18.6 migrations and five marked integration tests.

The full four-job workflow passed in run [37463724854](https://github.com/XanoSage/famaly-cash-flow/actions/runs/37463724854)
on commit `46e4ed0679186e9714e0aef4469d810773a70f4f`. It ran seven PostgreSQL integration tests,
and the full-stack Playwright 1.63.0/Chromium journey passed against a freshly migrated PostgreSQL
18.6 database. The workflow duration was 1m 22s; detailed results are recorded in
[`current-state-2026-10.md`](current-state-2026-10.md).

## Branching

Перед первой реализацией создаем ветку `staging` от `main`.

Порядок:

1. `main` хранит production-ready историю.
2. `staging` используется для интеграции и staging deploy.
3. `feature/*` используется для отдельных задач.

## Later

- Автоматические миграции с контролем.
- Preview environments для feature branches.
- Более полный production release workflow.
