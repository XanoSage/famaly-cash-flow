from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.user import User, UserPreference


class DefaultAccountError(ValueError):
    pass


class AccountPreferenceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self, *, family_id: UUID) -> list[Account]:
        return self.db.scalars(
            select(Account)
            .where(Account.family_id == family_id, Account.is_active.is_(True))
            .order_by(Account.name, Account.id)
        ).all()

    def get_default(
        self,
        *,
        user_id: UUID,
        family_id: UUID,
    ) -> Account | None:
        preference = self.db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
        if preference is None or preference.default_account_id is None:
            return None
        return self.db.scalar(
            select(Account).where(
                Account.id == preference.default_account_id,
                Account.family_id == family_id,
                Account.is_active.is_(True),
            )
        )

    def set_default(
        self,
        *,
        user_id: UUID,
        family_id: UUID,
        account_id: UUID,
    ) -> Account:
        user = self.db.scalar(
            select(User).where(
                User.id == user_id,
                User.family_id == family_id,
                User.is_active.is_(True),
            )
        )
        if user is None:
            raise DefaultAccountError("Account selection is not available.")

        account = self.db.scalar(
            select(Account).where(
                Account.id == account_id,
                Account.family_id == family_id,
                Account.is_active.is_(True),
            )
        )
        if account is None:
            raise DefaultAccountError("Account not found.")

        preference = self.db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
        if preference is None:
            preference = UserPreference(user_id=user_id, default_account_id=account.id)
            self.db.add(preference)
        else:
            preference.default_account_id = account.id
        self.db.commit()
        return account
