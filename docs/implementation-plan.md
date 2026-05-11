# Implementation Plan

Практический план реализации MVP Family Cash Flow.

Цель плана: перейти от согласованного ТЗ к разработке маленькими проверяемыми срезами.

## Principles

- Начинаем с рабочего skeleton, а не с большого абстрактного фреймворка.
- Каждый этап должен оставлять проект в запускаемом состоянии.
- Backend важнее на старте: данные, импорт, категории и тесты формируют основу продукта.
- Frontend подключается рано, но сначала на простых API и mock/minimal данных.
- Реальные банковские файлы не коммитятся.
- Synthetic sample можно хранить в репозитории.
- Sanitized реальные файлы храним вне Git.

## Phase 0 - Repo And Branch Setup

Цель: подготовить рабочий Git workflow.

Задачи:

- Убедиться, что `main` синхронизирован с GitHub.
- Создать ветку `staging` от `main`.
- Зафиксировать правило: feature branches создаются от `staging`.
- Добавить `.env.example` позже вместе с backend skeleton.

Definition of done:

- `main` чистый и запушен.
- `staging` существует локально и на GitHub.

## Phase 1 - Monorepo Skeleton

Цель: создать структуру проекта.

Структура:

```text
backend/
frontend/
infra/
docs/
README.md
```

Задачи:

- Создать `backend/`.
- Создать `frontend/`.
- Создать `infra/`.
- Добавить минимальные README внутри крупных папок, если нужно.

Definition of done:

- Структура создана.
- Проект все еще чисто коммитится.

## Phase 2 - Backend Skeleton

Цель: поднять минимальный FastAPI backend.

Задачи:

- Настроить Python project.
- Добавить FastAPI app.
- Добавить `/api/v1/health`.
- Добавить базовую структуру:
  - `api/routes`;
  - `core`;
  - `db`;
  - `models`;
  - `schemas`;
  - `services`;
  - `repositories`;
  - `importers`;
  - `analytics`;
  - `auth`.
- Добавить базовый pytest.

Definition of done:

- Backend запускается локально.
- Health endpoint отвечает.
- Есть хотя бы один тест health endpoint или service-level smoke test.

## Phase 3 - Database And Migrations

Цель: подключить PostgreSQL и миграции.

Задачи:

- Добавить Docker Compose с PostgreSQL.
- Настроить SQLAlchemy.
- Настроить Alembic.
- Добавить первые модели:
  - Family;
  - User;
  - Account;
  - PaymentInstrument;
  - Category;
  - Subcategory;
  - Merchant;
  - CategorizationRule.
- Добавить seed системных категорий из [Category Taxonomy](category-taxonomy.md).

Definition of done:

- Docker Compose поднимает Postgres.
- Миграции применяются.
- Seed категорий работает.

## Phase 4 - Auth MVP

Цель: сделать закрытый доступ для двух пользователей семьи.

Задачи:

- Email/password login.
- Password hashing.
- Access token.
- Refresh token.
- `/api/v1/auth/me`.
- User preferences: language `ru`/`uk`.

Definition of done:

- Можно создать тестового пользователя.
- Можно залогиниться.
- Можно получить текущего пользователя.
- Тесты покрывают базовый login flow.

## Phase 5 - XLSX Parser Spike

Цель: разобрать известный банковский XLSX формат.

Задачи:

- Реализовать parser для листа `Виписки`.
- Читать заголовки со строки 2.
- Читать данные со строки 3.
- Нормализовать:
  - date/time;
  - signed amount in UAH;
  - transaction amount/currency;
  - bank category;
  - description;
  - payment instrument.
- Добавить parser tests на synthetic XLSX.

Definition of done:

- Parser возвращает нормализованные rows.
- Тесты проверяют даты, суммы, валюты, описание и payment instrument.

## Phase 6 - Import Preview Backend

Цель: сделать draft import и preview flow.

Задачи:

- `POST /api/v1/imports/xlsx/preview`.
- ImportBatch со статусом `draft`.
- ImportPreviewRow.
- Preview statuses:
  - `auto_ready`;
  - `needs_review`;
  - `duplicate_candidate`;
  - `excluded`;
  - `error`.
- Reason codes.
- Duplicate detection fallback:
  - date;
  - amount;
  - description;
  - payment instrument.
- Draft auto-expiration metadata, 7 days.

Definition of done:

- XLSX можно загрузить и получить draft preview.
- Preview rows сохраняются в БД.
- Возможные дубли помечаются.
- Ошибочные строки не ломают весь импорт.

## Phase 7 - Categorization Engine

Цель: автоматически предлагать категории и правила.

Задачи:

- Bank category mapping.
- Merchant rules.
- Keyword rules.
- Rule priority.
- Rule conflict -> `needs_review`.
- Work/FOP candidates.
- Savings detection.
- Person transfer detection.

Definition of done:

- Супермаркеты маппятся в `Еда / Супермаркеты`.
- `Скарбничка` маппится в накопления.
- Переводы и реквизиты идут на review.
- Конфликт правил виден через reason code.

## Phase 8 - Import Confirmation

Цель: подтвердить импорт и создать реальные transactions.

Задачи:

- `GET /api/v1/imports/{id}/preview-rows`.
- `PATCH /api/v1/imports/{id}/preview-rows/{row_id}`.
- `POST /api/v1/imports/{id}/bulk-actions`.
- `POST /api/v1/imports/xlsx/confirm`.
- Final summary.
- Error blocking rules.
- Uncategorized allowed with warning.
- ImportBatch confirmed stats.

Definition of done:

- Пользователь может исправить preview row.
- Можно применить bulk action.
- Можно подтвердить импорт.
- Transactions создаются.
- ImportBatch сохраняет статистику.

## Phase 9 - Transactions API

Цель: дать приложению рабочий список операций.

Задачи:

- `GET /api/v1/transactions`.
- Offset/limit pagination.
- Filters:
  - period;
  - category;
  - merchant;
  - scope;
  - flow type;
  - uncategorized;
  - payment instrument;
  - original currency.
- `PATCH /api/v1/transactions/{id}`.
- Soft delete.
- AuditLog для изменений.

Definition of done:

- Таблица операций может получить данные.
- Операцию можно исправить.
- Soft delete исключает операцию из аналитики.

## Phase 10 - Analytics API

Цель: обеспечить дашборд данными.

Задачи:

- Summary.
- Timeline day/week/month.
- By category.
- By merchant.
- Savings.
- Uncategorized block.
- Work/FOP block.
- Budget risk placeholders.

Definition of done:

- Дашборд может отобразить основные KPI.
- Категории и merchants агрегируются корректно.

## Phase 11 - Frontend Skeleton

Цель: создать React приложение и shell.

Задачи:

- Vite + React + TypeScript.
- Routing.
- App shell:
  - sidebar;
  - top bar;
  - language switch/user;
  - notifications placeholder.
- API client.
- Basic auth flow.

Definition of done:

- Frontend запускается локально.
- Есть login shell и пустые страницы разделов.

## Phase 12 - Import UI

Цель: сделать первый полезный пользовательский экран.

Задачи:

- Upload XLSX.
- Import summary.
- Preview table.
- Filters.
- Row edit drawer/basic controls.
- Bulk actions.
- Final summary.
- Confirm import.

Definition of done:

- Пользователь может пройти upload -> review -> confirm.

## Phase 13 - Operations And Dashboard UI

Цель: дать базовую ежедневную пользу.

Задачи:

- Transactions table.
- Filters.
- Edit drawer.
- Manual transaction form.
- Cash short form.
- Dashboard KPI cards.
- Timeline chart.
- Category bar chart.
- Top merchants.
- Savings block.
- Uncategorized block.

Definition of done:

- После импорта пользователь видит аналитику и может исправлять операции.

## Phase 14 - Budgets And Notifications MVP

Цель: добавить контроль расходов.

Задачи:

- Draft budget from imported data.
- Total monthly budget.
- Category limits.
- 80% warning.
- 100% exceeded.
- In-app notifications.

Definition of done:

- Пользователь видит бюджетный прогресс.
- Превышения и предупреждения отображаются внутри приложения.

## Phase 15 - DevOps MVP

Цель: подготовить путь к staging.

Задачи:

- Backend Dockerfile.
- Frontend build config.
- GitHub Actions:
  - backend tests;
  - frontend build;
  - Docker image build later;
  - staging deploy later.
- Cloud Run staging notes.
- Firebase Hosting staging notes.

Definition of done:

- Есть локальный Docker путь.
- CI хотя бы проверяет backend tests и frontend build.

## First Coding Session Recommendation

Начать с:

1. Создать `staging` ветку.
2. Создать `feature/monorepo-skeleton`.
3. Добавить папки `backend`, `frontend`, `infra`.
4. Поднять backend health endpoint.
5. Добавить Docker Compose с Postgres.
6. Сделать первый маленький PR/merge в `staging`.

