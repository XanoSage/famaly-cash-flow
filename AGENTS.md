# Repository guidance for Codex

Before modifying code, read `README.md`, `docs/current-state-2026-10.md`,
`docs/product-requirements.md`, `docs/mvp-scope.md`, `docs/architecture.md`, and the
feature documents relevant to the change.

- PostgreSQL is the source of truth for application data.
- Use `Decimal` for financial calculations; do not use floating point for money.
- Change database schemas through Alembic migrations. Review generated migrations before use.
- Web and Telegram must call the same application/domain services for shared behavior.
- Financial data is sensitive. Do not casually log transaction descriptions, amounts, bank rows,
  Telegram message text, or uploaded statement contents.
- Add tests for new business logic and changes to financial behavior.
- Preserve the existing Python/FastAPI, PostgreSQL, SQLAlchemy, Alembic, Pytest,
  React/TypeScript/Vite architecture. Do not redesign it without a concrete technical or product
  reason; explain that reason before making broad changes.
