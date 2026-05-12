# Backend

FastAPI backend for Family Cash Flow.

## Local Commands

Install dependencies from the repository root:

```bash
cd backend
python -m pip install -e ".[dev]"
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Local PostgreSQL is exposed on port `5433` to avoid conflicts with a PostgreSQL instance installed on Windows.

Run tests:

```bash
pytest
```

Apply migrations:

```bash
alembic upgrade head
```

Seed system categories:

```bash
python -m app.db.seed_system_categories
```

Health endpoint:

```text
GET /api/v1/health
```

