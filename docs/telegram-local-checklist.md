# Telegram Local Checklist

This checklist is for the first real Telegram bot smoke test against local backend and demo data.

## 1. Prepare Backend Data

From `backend`:

```powershell
docker compose up -d postgres
alembic upgrade head
python -m app.db.seed_system_categories
python -m app.db.seed_demo_dashboard
```

Copy both values printed by demo seed:

- `Demo family_id`
- `Demo account_id`

## 2. Fill Backend Env

In backend `.env`:

```env
TELEGRAM_BOT_TOKEN=<bot token from BotFather>
TELEGRAM_WEBHOOK_SECRET_TOKEN=<random local secret>
TELEGRAM_DEFAULT_FAMILY_ID=<Demo family_id>
TELEGRAM_DEFAULT_ACCOUNT_ID=<Demo account_id>
```

`TELEGRAM_DEFAULT_FAMILY_ID` and `TELEGRAM_DEFAULT_ACCOUNT_ID` are temporary MVP shortcuts until Telegram users are linked to real Family Cash Flow users/families in the database.

## 3. Run Backend

From `backend`:

```powershell
uvicorn app.main:app --reload
```

Local webhook endpoint:

```text
POST http://127.0.0.1:8000/api/v1/telegram/webhook
```

Telegram needs a public HTTPS URL. For local testing, expose the backend with a tunnel such as ngrok or cloudflared, then set Telegram webhook to:

```text
https://<public-tunnel-host>/api/v1/telegram/webhook
```

When setting the webhook, pass the same secret as `X-Telegram-Bot-Api-Secret-Token`.

## 4. Manual Bot Smoke Test

Send these messages to the bot:

```text
/start
/summary
/review
```

In `/review`:

- press `Готово N` to clear `needs_review`;
- press `Категория N`, then choose a category to assign it and clear `needs_review`.

Manual transaction input:

```text
АТБ 450 еда
Рынок 120 неизвестно
```

Expected behavior:

- known category hint creates an expense without review;
- unknown category hint creates an expense with `needs_review=true`;
- `/review` should show operations still needing review.

## 5. Backend Verification

After bot actions, check the dashboard or API:

```text
GET /api/v1/analytics/summary?family_id=<Demo family_id>
GET /api/v1/transactions?family_id=<Demo family_id>&needs_review=true
```
