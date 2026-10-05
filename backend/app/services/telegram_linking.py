from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.telegram_identity import TelegramIdentity, TelegramLinkToken
from app.models.user import User

TELEGRAM_LINK_TOKEN_LIFETIME = timedelta(minutes=15)
_RAW_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,64}$")


class TelegramAlreadyLinkedError(ValueError):
    pass


@dataclass(frozen=True)
class CreatedTelegramLink:
    token: str
    expires_at: datetime
    telegram_url: str | None


def create_telegram_link(
    db: Session,
    *,
    user_id: UUID,
    bot_username: str | None,
) -> CreatedTelegramLink:
    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None:
        raise ValueError("Active user not found.")

    existing_identity = db.scalar(
        select(TelegramIdentity).where(
            TelegramIdentity.user_id == user_id,
            TelegramIdentity.is_active.is_(True),
        )
    )
    if existing_identity is not None:
        raise TelegramAlreadyLinkedError("Unlink Telegram before creating a new link.")

    now = datetime.now(UTC)
    db.execute(
        update(TelegramLinkToken)
        .where(
            TelegramLinkToken.user_id == user_id,
            TelegramLinkToken.used_at.is_(None),
            TelegramLinkToken.expires_at > now,
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )

    raw_token = secrets.token_urlsafe(32)
    expires_at = now + TELEGRAM_LINK_TOKEN_LIFETIME
    db.add(
        TelegramLinkToken(
            user_id=user_id,
            token_hash=hash_telegram_link_token(raw_token),
            expires_at=expires_at,
        )
    )
    db.commit()

    telegram_url = None
    normalized_username = bot_username.strip().lstrip("@") if bot_username else ""
    if normalized_username:
        telegram_url = f"https://t.me/{quote(normalized_username)}?start={quote(raw_token)}"
    return CreatedTelegramLink(token=raw_token, expires_at=expires_at, telegram_url=telegram_url)


def hash_telegram_link_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def consume_telegram_link_token(
    db: Session,
    *,
    raw_token: str,
    telegram_user_id: int,
    private_chat_id: int,
    profile: dict[str, object],
) -> bool:
    if not _RAW_TOKEN_PATTERN.fullmatch(raw_token) or telegram_user_id <= 0 or private_chat_id <= 0:
        return False

    now = datetime.now(UTC)
    token = db.scalar(
        select(TelegramLinkToken)
        .where(
            TelegramLinkToken.token_hash == hash_telegram_link_token(raw_token),
            TelegramLinkToken.used_at.is_(None),
            TelegramLinkToken.expires_at > now,
        )
        .with_for_update()
    )
    if token is None:
        return False

    user = db.scalar(select(User).where(User.id == token.user_id, User.is_active.is_(True)))
    if user is None:
        db.rollback()
        return False

    existing_identities = db.scalars(
        select(TelegramIdentity)
        .where(
            or_(
                TelegramIdentity.telegram_user_id == telegram_user_id,
                TelegramIdentity.user_id == user.id,
            )
        )
        .with_for_update()
    ).all()
    if any(identity.is_active for identity in existing_identities):
        return False

    consumed = db.execute(
        update(TelegramLinkToken)
        .where(
            TelegramLinkToken.id == token.id,
            TelegramLinkToken.used_at.is_(None),
            TelegramLinkToken.expires_at > now,
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if consumed.rowcount != 1:
        db.rollback()
        return False

    if existing_identities:
        db.execute(
            delete(TelegramIdentity).where(
                TelegramIdentity.id.in_([identity.id for identity in existing_identities]),
                TelegramIdentity.is_active.is_(False),
            )
        )

    db.add(
        TelegramIdentity(
            user_id=user.id,
            telegram_user_id=telegram_user_id,
            private_chat_id=private_chat_id,
            username=_profile_value(profile, "username", 64),
            first_name=_profile_value(profile, "first_name", 128),
            last_name=_profile_value(profile, "last_name", 128),
            linked_at=now,
            last_seen_at=now,
            is_active=True,
        )
    )
    try:
        db.flush()
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def get_active_telegram_identity(db: Session, *, user_id: UUID) -> TelegramIdentity | None:
    return db.scalar(
        select(TelegramIdentity).where(
            TelegramIdentity.user_id == user_id,
            TelegramIdentity.is_active.is_(True),
        )
    )


def unlink_telegram_identity(db: Session, *, user_id: UUID) -> bool:
    now = datetime.now(UTC)
    identity = db.scalar(
        select(TelegramIdentity)
        .where(
            TelegramIdentity.user_id == user_id,
            TelegramIdentity.is_active.is_(True),
        )
        .with_for_update()
    )
    db.execute(
        update(TelegramLinkToken)
        .where(
            TelegramLinkToken.user_id == user_id,
            TelegramLinkToken.used_at.is_(None),
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if identity is None:
        db.commit()
        return False
    identity.is_active = False
    db.commit()
    return True


def _profile_value(profile: dict[str, object], key: str, max_length: int) -> str | None:
    value = profile.get(key)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized[:max_length] or None
