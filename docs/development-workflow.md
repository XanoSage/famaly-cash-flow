# Development Workflow

## Режим разработки

Работа идет в смешанном режиме:

- важные архитектурные и backend-решения объясняются подробно;
- рутинный код пишется быстрее;
- по ходу проекта добавляются короткие учебные заметки в Markdown.

## Учебный фокус

Проект должен показывать полный backend-путь:

- FastAPI routes как аналог controllers;
- services для бизнес-логики;
- repositories для доступа к данным;
- Pydantic schemas как DTO;
- SQLAlchemy models как persistence layer;
- Alembic migrations;
- Docker;
- Google Cloud Run deployment;
- CI/CD.

По ходу разработки полезно иногда сравнивать решения с NestJS и ASP.NET Core.

## Git Workflow

Ветки:

- `main` - production-ready версия;
- `staging` - интеграция и staging deployment;
- `feature/*` - отдельные задачи.

Обычный поток:

1. Создать `feature/*` ветку.
2. Реализовать задачу.
3. Проверить тесты и сборку.
4. Слить в `staging`.
5. Проверить staging.
6. При готовности перенести в `main`.

## Task Management

Пока задачи ведутся в [backlog.md](backlog.md). После появления GitHub-репозитория задачи можно перенести в GitHub Issues.

