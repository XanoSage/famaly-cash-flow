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

GitHub Actions:

- backend tests;
- frontend build;
- Docker image build;
- deploy backend to Cloud Run staging при push/merge в `staging`;
- deploy frontend to Firebase Hosting staging;
- production deploy запускается вручную.

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
