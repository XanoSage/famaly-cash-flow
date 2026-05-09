# Deployment Google Cloud

## Цель

Показать полный путь backend-сервиса:

1. Написать FastAPI backend.
2. Упаковать backend в Docker image.
3. Запустить локально через Docker Compose.
4. Опубликовать image в Artifact Registry.
5. Задеплоить backend в Google Cloud Run.
6. Подключить Cloud SQL for PostgreSQL.

## Целевая схема

```text
React Frontend on Firebase Hosting -> FastAPI on Cloud Run -> Cloud SQL PostgreSQL
```

## Локальная разработка

```text
Docker Compose:
  backend
  postgres
```

Первый deploy target:

1. local Docker Compose;
2. затем staging backend на Cloud Run;
3. затем staging frontend на Firebase Hosting.

## Google Cloud компоненты

- Cloud Run - запуск backend container.
- Firebase Hosting - размещение frontend.
- Cloud SQL for PostgreSQL - production database.
- Artifact Registry - хранение container images.
- Secret Manager - хранение секретов.

## Окружения

- local;
- staging;
- production.

Staging используется для проверки деплоя и обезличенных данных. Production используется для реальных семейных данных.

## Почему Cloud Run

Cloud Run подходит для MVP, потому что запускает контейнеры без управления серверами и хорошо подходит для API-сервисов. Это позволяет учиться контейнеризации и деплою, не поднимая Kubernetes.

## Что уточнить позже

- Google Cloud project id.
- Region.
- Нужен ли публичный endpoint или только закрытый доступ.
- Где будет размещаться frontend.
- Нужен ли custom domain.
- Стратегия миграций Alembic в production.

## Migrations

Staging:

- сначала допустим ручной запуск или отдельная CI job;
- миграции проходят review перед применением.

Production:

- миграции запускаются вручную после подтверждения.
