# Security

## MVP Auth

- Email/password.
- Email is trimmed/lowercased and globally unique while each user belongs to one family.
- Passwords use Argon2; plaintext passwords are never stored.
- Short-lived HS256 access JWT; `sub` is the application user UUID and no family claim is trusted.
- Refresh tokens are random opaque values. PostgreSQL stores only their SHA-256 hashes in
  `auth_sessions`; refresh rotates the hash and revocation/rotation prevents reuse.
- Refresh token is an HttpOnly cookie. Local development uses `SameSite=Lax` and HTTP; production
  requires a non-placeholder JWT secret and Secure cookies.
- Authenticated APIs load the persisted user and derive the family from `User.family_id`.
- Cross-family entity IDs are rejected by backend route/service checks.

Production frontend/API deployments should use the same site under a custom domain. If they must be
cross-site, configure `AUTH_COOKIE_SAMESITE=none`, `AUTH_COOKIE_SECURE=true`, HTTPS, and credentialed
CORS for the exact frontend origin. Browsers may block third-party cookies, so same-site hosting is
the supported deployment shape.

## Telegram Identity and Webhook

- The authenticated Web user creates a random 32-byte, 15-minute link token. Only its SHA-256 hash
  is stored. A conditional update and row lock consume it once; PostgreSQL locking behavior is
  covered by design but still requires live PostgreSQL verification.
- Telegram is identified by numeric `from.id`; usernames are display metadata and `chat.id` is
  used only to reply. A unique database constraint allows one identity per user and Telegram ID.
- Telegram family access is derived from the linked application user. Financial commands and
  callbacks require a private chat; callback sender identity is resolved on every update.
- Unlink marks the identity inactive and expires outstanding link tokens in the same request.
- Configure `TELEGRAM_WEBHOOK_SECRET_TOKEN` in production whenever `TELEGRAM_BOT_TOKEN` is set.
  Compare the received header in constant time.
- Never log the raw link token, Telegram update text, bot token, webhook secret, or financial data.

New Telegram manual timestamps are assigned as timezone-aware UTC instants. Display dates use the
family's Europe/Kyiv timezone policy. Imported bank timestamps remain a separate unresolved
timezone issue.

## Хранение данных

- Финансовые операции хранятся в PostgreSQL.
- Исходные XLSX-файлы после обработки не хранятся.
- Метаданные импорта сохраняются.
- В базе не нужно хранить полный номер карты. Если банк отдает маску карты, сохраняем только маску или последние цифры.

## Transport Security

- В production используется HTTPS.
- Cloud Run предоставляет HTTPS endpoint.

## Будущие улучшения

- Двухфакторная авторизация.
- Google Login.
- Шифрование особо чувствительных данных на уровне приложения.
- Audit log действий пользователя.
- Ограничение доступа по IP или VPN, если понадобится.

## Важные требования

- Пароли никогда не хранятся в открытом виде.
- Secrets не коммитятся в Git.
- Production secrets должны храниться в Secret Manager или аналогичном сервисе.
- Логи не должны содержать полные банковские выписки или пароли.
- Логи импорта не должны содержать полный список операций.
- JWTs, refresh tokens, password hashes, and financial payloads must not be logged.
