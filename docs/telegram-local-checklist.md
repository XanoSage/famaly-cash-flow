# Telegram Local Checklist

This checklist exercises the real Bot API. It requires bot credentials and a public HTTPS tunnel;
unit tests do not replace this smoke test.

## 1. Prepare the Application

From the repository root, set local-only values in `.env` and copy the file to `backend/.env`:

```env
DEMO_USER_EMAIL=you@example.test
DEMO_USER_PASSWORD=<local password>
TELEGRAM_BOT_TOKEN=<token from BotFather>
TELEGRAM_BOT_USERNAME=<bot username without @>
TELEGRAM_WEBHOOK_SECRET_TOKEN=<random local secret>
```

Start PostgreSQL and prepare the demo user:

```powershell
docker compose up -d postgres
Set-Location backend
python -m alembic upgrade head
python -m app.db.seed_system_categories
python -m app.db.seed_demo_dashboard
python -m uvicorn app.main:app --reload
```

Use the credentials from `.env` to sign in at `http://localhost:5173/`.

## 2. Set the Telegram Webhook

Expose the backend with an HTTPS tunnel such as ngrok or cloudflared, then register
`https://<public-tunnel-host>/api/v1/telegram/webhook` with Telegram using
`TELEGRAM_WEBHOOK_SECRET_TOKEN` as the webhook secret token.

## 3. Link the Telegram Account

In the signed-in Web account area:

1. Select **Create link**.
2. Open the Telegram deep link before its displayed expiration time.
3. Send `/start <token>` in the private bot conversation.
4. Return to Web and refresh the Telegram status. It should show the linked account.

The link expires after 15 minutes and can be used once. If it expires, generate another from Web.
Do not share the link or token. No family or account IDs are entered in Telegram configuration.

## 4. Check Telegram Workflows

Send these messages in the private bot conversation:

```text
/summary
/review
/account
АТБ 450 еда
Рынок 120 неизвестно
```

Choose an account with `/account`. A known category hint should create a categorized expense;
an unknown hint should create an expense that needs review. Review buttons should mark an
operation reviewed or assign a category.

Financial commands in a group must not return family data. Unlink Telegram from Web and confirm
that subsequent commands receive an unlinked response.

## 5. Verify Data

Check the authenticated dashboard and transaction list in Web. Do not use client-supplied
`family_id` values as an authorization mechanism.
