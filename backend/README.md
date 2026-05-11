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

Run tests:

```bash
pytest
```

Health endpoint:

```text
GET /api/v1/health
```

