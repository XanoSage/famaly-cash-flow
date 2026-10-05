# Roadmap

## Phase 1 - Documentation And Setup

- Создать документацию проекта.
- Зафиксировать MVP scope.
- Подготовить структуру репозитория.
- Настроить backend, frontend и Docker Compose.
- Инициализировать Git workflow `main`, `staging`, `feature/*`.

## Phase 2 - Backend Core

- FastAPI app.
- PostgreSQL connection.
- SQLAlchemy models.
- Alembic migrations.
- Auth.
- Базовые CRUD endpoints.

## Phase 3 - XLSX Import

- Парсер XLSX.
- Preview импорта.
- Проверка дублей.
- Подтверждение импорта.
- Метаданные импорта.

## Phase 4 - Categorization

- Стартовый набор категорий.
- Правила ключевых слов.
- Правила продавец -> категория.
- Ручные исправления.

## Phase 5 - Analytics

- Summary.
- By category.
- By merchant.
- Timeline.
- Простые инсайты.

## Phase 6 - Frontend MVP

- Логин.
- Dashboard.
- Import flow.
- Transactions table.
- Categories.
- Merchants.
- Cash.

## Phase 7 - Telegram Core Client

- Link a Telegram `from.id` to an authenticated application user using expiring one-time tokens.
- Derive family access from the linked user and limit financial commands to private chats.
- Provide quick manual entry, summaries, review actions, category correction, and account selection.
- Keep Telegram link controls in the authenticated Web account area.
- Add identity, family-isolation, replay, account-selection, and manual-entry tests.

## Phase 8 - Deployment

- Dockerfile.
- Docker Compose.
- Google Cloud Run.
- Firebase Hosting.
- Cloud SQL.
- GitHub Actions для staging deploy и ручного production deploy.
- Production configuration.

## Later

- Telegram notifications and Mini App.
- Лимиты и бюджеты.
- Сравнение периодов.
- Аномалии.
- AI-отчеты.
- Google Login.
- 2FA.
- Учет карт жены.
- Мультивалютность.
