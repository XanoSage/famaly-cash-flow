# Family Cash Flow

Семейный сервис для учета движения денег: импорт банковских XLSX-выписок, ручной учет наличных, автокатегоризация операций, аналитика расходов и рекомендации.

Проект одновременно решает практическую задачу семейного бюджета и служит учебным backend-проектом: от FastAPI-контроллеров и PostgreSQL до Docker, тестов и деплоя в Google Cloud Run.

## Документация

- [Product Requirements](docs/product-requirements.md)
- [MVP Scope](docs/mvp-scope.md)
- [Architecture](docs/architecture.md)
- [Data Model](docs/data-model.md)
- [API Design](docs/api-design.md)
- [XLSX Import](docs/xlsx-import.md)
- [Import Preview Flow](docs/import-preview-flow.md)
- [Bank XLSX Analysis](docs/bank-xlsx-analysis.md)
- [Categorization](docs/categorization.md)
- [Category Taxonomy](docs/category-taxonomy.md)
- [Analytics And Recommendations](docs/analytics-and-recommendations.md)
- [Dashboard And Reports](docs/dashboard-and-reports.md)
- [Operations And Cash](docs/operations-and-cash.md)
- [Budgets Notifications Recommendations](docs/budgets-notifications-recommendations.md)
- [UI/UX](docs/ui-ux.md)
- [UI Wireframes](docs/ui-wireframes.md)
- [Localization](docs/localization.md)
- [Security](docs/security.md)
- [Deployment Google Cloud](docs/deployment-google-cloud.md)
- [Development Workflow](docs/development-workflow.md)
- [Environments And CI/CD](docs/environments-and-cicd.md)
- [API Contract Decisions](docs/api-contract-decisions.md)
- [Implementation Readiness](docs/implementation-readiness.md)
- [Implementation Plan](docs/implementation-plan.md)
- [Remaining TZ Questions](docs/remaining-tz-questions.md)
- [Learning Notes](docs/learning-notes.md)
- [Testing](docs/testing.md)
- [Roadmap](docs/roadmap.md)
- [Backlog](docs/backlog.md)

## Зафиксированные решения

- MVP: веб-приложение для тебя и жены.
- Backend: Python FastAPI + PostgreSQL.
- Frontend: React + Vite + TypeScript.
- Импорт: XLSX-выписка банка, preview перед подтверждением.
- Дополнительно: ручной ввод наличных операций.
- Валюта MVP: основной счет в UAH, при этом импорт сохраняет валюту оригинальной транзакции, если банк ее отдает.
- Языки интерфейса и отчетов: русский и украинский.
- Структура проекта: монорепозиторий с `backend`, `frontend`, `infra`, `docs`.
- Деплой: backend в Google Cloud Run, frontend в Firebase Hosting, база в Cloud SQL for PostgreSQL.
- Окружения: local, staging, production.
- Git workflow: `main`, `staging`, `feature/*`.
- API: REST under `/api/v1`, FastAPI OpenAPI plus Markdown schemas.
- ТЗ считается готовым к старту реализации после обновления docs, короткого implementation plan и минимальных wireframe-описаний UI.
