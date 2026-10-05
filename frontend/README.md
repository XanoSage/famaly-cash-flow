# Frontend

React + Vite + TypeScript frontend for Family Cash Flow.

From the repository root:

```powershell
Set-Location frontend
npm ci
npm run dev -- --host localhost
npm run build
```

Open `http://localhost:5173/`. The app calls `http://localhost:8000/api/v1` by default, shows a
login form, and loads the family attached to the authenticated user. It does not ask for a family
UUID.

Override the API URL if needed:

```powershell
$env:VITE_API_BASE_URL = "http://localhost:8000/api/v1"
npm run dev -- --host localhost
```

The API access token stays in memory. The refresh token is an HttpOnly cookie and is sent with
credentialed requests. For local development, use `localhost` consistently for the frontend and API.
