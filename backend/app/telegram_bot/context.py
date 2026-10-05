from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.account import Account
from app.models.family import Family
from app.models.telegram_identity import TelegramIdentity
from app.models.user import User
from app.services.account_preferences import AccountPreferenceService

UNLINKED_TELEGRAM_TEXT = (
    "Сначала свяжите этот Telegram-аккаунт с пользователем в веб-приложении Family Cash Flow."
)
PRIVATE_CHAT_ONLY_TEXT = "Для финансовых команд откройте личный чат с ботом."
LINK_FAILURE_TEXT = (
    "Не удалось связать аккаунт. Создайте новую ссылку в веб-приложении и попробуйте ещё раз."
)
START_TEXT = (
    "Чтобы начать, войдите в Family Cash Flow Web и создайте ссылку в разделе Telegram.\n\n"
    "Доступны команды: /summary, /review и /account."
)


@dataclass(frozen=True)
class TelegramRequestContext:
    identity: TelegramIdentity
    user: User
    family: Family
    private_chat_id: int
    default_account: Account | None


def resolve_telegram_context(
    db: Session,
    *,
    telegram_user_id: int,
    private_chat_id: int,
    profile: dict[str, object] | None = None,
) -> TelegramRequestContext | None:
    if telegram_user_id <= 0 or private_chat_id <= 0:
        return None

    identity = db.scalar(
        select(TelegramIdentity)
        .where(
            TelegramIdentity.telegram_user_id == telegram_user_id,
            TelegramIdentity.is_active.is_(True),
        )
        .with_for_update()
    )
    if identity is None:
        return None

    user = db.scalar(
        select(User)
        .options(joinedload(User.family))
        .where(User.id == identity.user_id, User.is_active.is_(True))
    )
    if user is None:
        return None

    now = datetime.now(UTC)
    identity.private_chat_id = private_chat_id
    identity.last_seen_at = now
    if profile is not None:
        identity.username = _profile_value(profile, "username", 64)
        identity.first_name = _profile_value(profile, "first_name", 128)
        identity.last_name = _profile_value(profile, "last_name", 128)

    family = user.family
    if family is None:
        return None
    account = AccountPreferenceService(db).get_default(user_id=user.id, family_id=family.id)
    return TelegramRequestContext(
        identity=identity,
        user=user,
        family=family,
        private_chat_id=private_chat_id,
        default_account=account,
    )


def _profile_value(profile: dict[str, object], key: str, max_length: int) -> str | None:
    value = profile.get(key)
    if not isinstance(value, str):
        return None
    return value.strip()[:max_length] or None
