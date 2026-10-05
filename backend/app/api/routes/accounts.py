from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.account import Account
from app.models.user import User, UserPreference
from app.schemas.accounts import AccountListResponse, AccountResponse

router = APIRouter(prefix="/accounts")


@router.get("", response_model=AccountListResponse)
def list_accounts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountListResponse:
    accounts = db.scalars(
        select(Account)
        .where(
            Account.family_id == current_user.family_id,
            Account.is_active.is_(True),
        )
        .order_by(Account.name, Account.id)
    ).all()
    default_account_id = db.scalar(
        select(UserPreference.default_account_id).where(UserPreference.user_id == current_user.id)
    )
    return AccountListResponse(
        rows=[
            AccountResponse(
                id=account.id,
                name=account.name,
                type=account.type,
                currency=account.currency,
                is_active=account.is_active,
                owner_user_id=account.owner_user_id,
                is_default=account.id == default_account_id,
            )
            for account in accounts
        ]
    )
