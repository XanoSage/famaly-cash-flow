from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user
from app.auth.service import (
    DUMMY_PASSWORD_HASH,
    access_token_expires_in,
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    normalize_email,
    verify_password,
)
from app.core.config import settings
from app.db.session import get_db
from app.models.user import AuthSession, User
from app.schemas.auth import AccessTokenResponse, CurrentUserResponse, LoginRequest

router = APIRouter(prefix="/auth")
REFRESH_COOKIE_NAME = "refresh_token"


@router.post("/login", response_model=AccessTokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    user = db.scalar(
        select(User)
        .options(joinedload(User.family), joinedload(User.preferences))
        .where(User.email == normalize_email(payload.email))
    )
    encoded_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_matches = verify_password(payload.password, encoded_hash)
    if user is None or not user.is_active or not password_matches:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    raw_refresh_token = new_refresh_token()
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(raw_refresh_token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    db.add(session)
    db.flush()
    access_token = create_access_token(user.id, session.id)
    db.commit()
    _set_refresh_cookie(response, raw_refresh_token)
    return AccessTokenResponse(access_token=access_token, expires_in=access_token_expires_in())


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh session is invalid.")

    session = db.scalar(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == hash_refresh_token(refresh_token))
        .with_for_update()
    )
    now = datetime.now(UTC)
    if session is None or session.revoked_at is not None or _as_utc(session.expires_at) <= now:
        raise HTTPException(status_code=401, detail="Refresh session is invalid.")

    user = db.scalar(
        select(User)
        .options(joinedload(User.family), joinedload(User.preferences))
        .where(User.id == session.user_id)
    )
    if user is None or not user.is_active:
        session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh session is invalid.")

    rotated_token = new_refresh_token()
    session.refresh_token_hash = hash_refresh_token(rotated_token)
    session.expires_at = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    db.flush()
    access_token = create_access_token(user.id, session.id)
    db.commit()
    _set_refresh_cookie(response, rotated_token)
    return AccessTokenResponse(access_token=access_token, expires_in=access_token_expires_in())


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
    db: Session = Depends(get_db),
) -> Response:
    if refresh_token:
        session = db.scalar(
            select(AuthSession).where(
                AuthSession.refresh_token_hash == hash_refresh_token(refresh_token),
                AuthSession.revoked_at.is_(None),
            )
        )
        if session is not None:
            session.revoked_at = datetime.now(UTC)
            db.commit()
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=CurrentUserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        display_name=current_user.display_name,
        email=current_user.email,
        language=current_user.preferences.language if current_user.preferences else "ru",
        family_id=current_user.family_id,
        family_name=current_user.family.name,
    )


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.effective_auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path=f"{settings.api_v1_prefix}/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=settings.effective_auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path=f"{settings.api_v1_prefix}/auth",
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
