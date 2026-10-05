from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.service import decode_access_token
from app.db.session import get_db
from app.models.user import AuthSession, User

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    decoded = decode_access_token(credentials.credentials)
    if decoded is None:
        raise unauthorized
    user_id, session_id = decoded
    now = datetime.now(UTC)
    user = db.scalar(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .options(joinedload(User.family), joinedload(User.preferences))
        .where(
            User.id == user_id,
            User.is_active.is_(True),
            AuthSession.id == session_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
    )
    if user is None:
        raise unauthorized
    return user
