# Frontend

React + Vite + TypeScript frontend for Family Cash Flow.

## Local Commands

```bash
npm install
npm run dev
npm run build
```

## API

By default the app calls:

```bash
http://localhost:8000/api/v1
```

Override it for another backend:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
```

For the MVP dashboard, paste a `family_id` from the database/imported data into the filter bar.

