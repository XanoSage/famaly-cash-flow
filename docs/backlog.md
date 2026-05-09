# Backlog

## Product

- [x] Уточнить стартовый список категорий и подкатегорий.
- [ ] Проанализировать реальную XLSX-выписку.
- [ ] Описать правила определения продавца.
- [x] Решить, как учитывать две карты из одного банковского источника.
- [x] Решить, как классифицировать `Скарбничка` и другие накопления.
- [ ] Решить, как отображать операции с transaction currency USD/EUR при account currency UAH.
- [x] Описать обработку переводов физлицам.
- [x] Описать обработку переводов жене.
- [x] Описать обработку платежей по реквизитам.
- [ ] Уточнить формат ручного ввода наличных.
- [ ] Уточнить первый набор графиков.
- [x] Описать RU/UK локализацию интерфейса и отчетов.
- [x] Зафиксировать гибридную структуру детских расходов.
- [x] Зафиксировать подход к взрослому и детскому спорту.
- [x] Зафиксировать стратегию банковских категорий и review rules.
- [x] Зафиксировать подход к подпискам.
- [x] Зафиксировать подход к рабочим/FOP операциям.
- [x] Зафиксировать подход к доходам.
- [x] Зафиксировать бюджеты и лимиты MVP.
- [x] Зафиксировать будущий Telegram bot scope.
- [x] Зафиксировать правила по еде, супермаркетам, доставке, воде и кофе.
- [x] Зафиксировать детскую категорию, школу, футбол и медицину ребенка.
- [x] Зафиксировать дом, услуги, рабочее/FOP, транспорт, авто, развлечения и путешествия.
- [x] Зафиксировать подписки, подарки, переводы и без категории.

## Backend

- [ ] Создать структуру `backend/app`.
- [ ] Настроить FastAPI.
- [ ] Настроить PostgreSQL.
- [ ] Настроить SQLAlchemy.
- [ ] Настроить Alembic.
- [ ] Реализовать auth.
- [ ] Реализовать модели данных.
- [ ] Реализовать XLSX preview endpoint.
- [ ] Реализовать confirm import endpoint.
- [ ] Реализовать transactions endpoints.
- [ ] Реализовать categories endpoints.
- [ ] Реализовать merchants endpoints.
- [ ] Реализовать analytics endpoints.

## Frontend

- [ ] Создать React + Vite + TypeScript app.
- [ ] Реализовать layout личного кабинета.
- [ ] Реализовать логин.
- [ ] Реализовать Dashboard.
- [ ] Реализовать Import page.
- [ ] Реализовать Transactions page.
- [ ] Реализовать Categories page.
- [ ] Реализовать Merchants page.
- [ ] Реализовать Cash page.

## Infrastructure

- [ ] Добавить Dockerfile для backend.
- [ ] Добавить Docker Compose для local dev.
- [ ] Добавить env examples.
- [ ] Подготовить Google Cloud deployment notes.
- [ ] Настроить Cloud Run deployment.
- [ ] Настроить Firebase Hosting deployment.
- [ ] Настроить Cloud SQL connection.
- [ ] Настроить GitHub Actions для tests/build.
- [ ] Настроить staging deploy.
- [ ] Настроить manual production deploy.

## Testing

- [ ] Unit tests для XLSX parser.
- [ ] Unit tests для categorization.
- [ ] Unit tests для duplicate detection.
- [ ] Unit tests для analytics.
- [ ] Integration tests для API.
