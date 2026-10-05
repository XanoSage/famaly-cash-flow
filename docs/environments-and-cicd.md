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
`staging`, `feature/**`, and `codex/**` and has three jobs:

- backend fast tests using the existing SQLite fixtures, dependency consistency, and Ruff checks on
  changed Python files only (`E`, `F`, `I` plus format check);
- PostgreSQL 18.6 integration tests against a dedicated disposable database, with a real Alembic
  upgrade, newest-revision downgrade/upgrade, and tests for auth refresh, Telegram identity linking,
  import confirmation/Decimal persistence, and PostgreSQL constraints;
- locked frontend install (`npm ci`), frontend tests, and TypeScript/Vite production build.

The PostgreSQL job waits for the service health check and a `pg_isready` probe. It requires its
integration flag and database URL. Its test fixture verifies a
database name ending in `_integration_test`, and truncates application data before each test. Do not
use a local development or shared database for this suite. The workflow does not publish images or
deploy to Cloud Run/Firebase; those remain separate DevOps work.

The recommended required branch checks after reviewing branch protection are the workflow jobs
`backend-tests`, `postgres-integration`, and `frontend`. This repository change does not alter GitHub
branch protection settings.

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
