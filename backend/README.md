# Backend

FastAPI backend for Family Cash Flow.

## Local setup and demo login

From the repository root, copy `.env.example` to `.env` and set `DEMO_USER_EMAIL` and
`DEMO_USER_PASSWORD` to local-only values. Keep the file out of Git. Copy the same file to
`backend/.env` when running the backend directly because settings are loaded from the backend
working directory.

Start PostgreSQL from the repository root:

```powershell
docker compose up -d postgres
```

Install backend dependencies and create the demo family/user:

```powershell
Set-Location backend
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m app.db.seed_system_categories
python -m app.db.seed_demo_dashboard
```

The seed command uses the configured demo email/password, stores an Argon2 password hash, and
creates the demo family, account, and dashboard transactions. It prints family/account IDs and the
transaction count, never the password.

Start the API in that terminal:

```powershell
python -m uvicorn app.main:app --reload
```

In another terminal, install and start the frontend:

```powershell
Set-Location frontend
npm ci
npm run dev -- --host localhost
```

Open `http://localhost:5173/` and sign in with `DEMO_USER_EMAIL` and `DEMO_USER_PASSWORD` from the
local `.env`. Use `localhost` for both frontend and API so the local refresh cookie stays same-site.

## Other commands

Run backend tests:

```powershell
Set-Location backend
python -m pytest
```

The API health check is `GET /api/v1/health`. Local PostgreSQL is exposed on port `5433`.
Compose does not automatically apply migrations or seed demo data; use the commands above.
