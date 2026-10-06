# Architecture

## Общий подход

Проект строится как монорепозиторий:

```text
backend/
frontend/
infra/
docs/
README.md
```

## Backend

Authenticated Web requests follow this path:

```text
Web user
  -> authenticated FastAPI request
  -> persisted current User
  -> User.family
  -> shared application/domain services
  -> PostgreSQL
```

Family scope is derived from the persisted current user. User-facing routes do not accept a
client-selected family ID as an authorization input.

Telegram identity is linked to the same application user with a short-lived Web-issued token:

```text
Telegram user
  -> TelegramIdentity
  -> application User
  -> User.family
  -> the same shared application/domain services
  -> PostgreSQL
```

The webhook maps immutable Telegram `from.id` through `TelegramIdentity`; it does not accept a
family identifier from the update. Financial commands and callbacks require a private chat. Web
mutations, Telegram manual expense/income entry, and Telegram review changes share
`TransactionService`. This service owns family checks, amount sign normalization, UTC timestamps,
merchant/category validation, soft deletion, and atomic `AuditLog` writes. PostgreSQL is the source
of truth; link tokens are stored as SHA-256 hashes and consumed with a conditional update.

Transaction edit history is append-only at the application level. Deleting a transaction sets
`deleted_at` and `deleted_by_user_id`; default transaction queries and analytics omit deleted rows.
Manual display-description edits use `description_override` so imported descriptions remain intact.

Стек MVP:

- Python;
- FastAPI;
- SQLAlchemy;
- PostgreSQL;
- Alembic для миграций;
- Pytest для тестов.

Ориентировочная структура backend:

```text
backend/
  app/
    main.py
    api/
      routes/
    core/
    db/
    models/
    schemas/
    services/
    repositories/
    importers/
    analytics/
    auth/
  tests/
  alembic/
  pyproject.toml
  Dockerfile
```

## Слои backend

- `routes` - FastAPI endpoints, аналог controllers.
- `schemas` - входные и выходные DTO на Pydantic.
- `services` - бизнес-логика.
- `repositories` - доступ к данным.
- `models` - SQLAlchemy-модели.
- `importers` - парсинг XLSX и нормализация операций.
- `analytics` - расчеты отчетов и инсайтов.
- `auth` - логин, пароли, токены.

В NestJS похожие сущности обычно назывались бы `controller`, `service`, `module`, `dto`, `entity`.

В ASP.NET Core похожая схема была бы `Controllers` или Minimal API endpoints, `Services`, `Repositories`, EF Core entities и DTO models.

## Frontend

Стек MVP:

- React;
- Vite;
- TypeScript;
- библиотека графиков: Recharts или ECharts;
- таблицы: сначала простая реализация, позже можно TanStack Table.

## Infrastructure

Локальная разработка:

- Docker Compose;
- backend container;
- PostgreSQL container.

Деплой:

- backend container -> Google Cloud Run;
- PostgreSQL -> Cloud SQL for PostgreSQL;
- container images -> Artifact Registry;
- HTTPS через Cloud Run.

