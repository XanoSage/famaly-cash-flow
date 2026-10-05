from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.category import Category
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.models.user import User


class ManualTransactionError(ValueError):
    pass


class ManualTransactionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_expense(
        self,
        *,
        user_id: UUID,
        family_id: UUID,
        account_id: UUID,
        description: str,
        raw_text: str,
        amount: Decimal,
        category_hint: str | None,
    ) -> Transaction:
        user = self.db.scalar(
            select(User).where(
                User.id == user_id,
                User.family_id == family_id,
                User.is_active.is_(True),
            )
        )
        if user is None:
            raise ManualTransactionError("User is not available in this family.")

        account = self.db.scalar(
            select(Account).where(
                Account.id == account_id,
                Account.family_id == family_id,
                Account.is_active.is_(True),
            )
        )
        if account is None:
            raise ManualTransactionError("Account not found.")

        category = self._find_category(family_id=family_id, hint=category_hint)
        merchant = self._get_or_create_merchant(family_id=family_id, name=description)
        transaction = Transaction(
            family_id=family_id,
            account_id=account.id,
            owner_user_id=user.id,
            occurred_at=datetime.now(UTC),
            amount=-abs(amount).quantize(Decimal("0.01")),
            currency=account.currency,
            direction="expense",
            flow_type="purchase",
            scope="family",
            description_raw=raw_text.strip(),
            description_normalized=description,
            merchant=merchant,
            category=category,
            comment=f"Telegram manual: {raw_text.strip()}",
            needs_review=category is None,
        )
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        return transaction

    def _find_category(self, *, family_id: UUID, hint: str | None) -> Category | None:
        if not hint:
            return None
        normalized_hint = hint.casefold()
        categories = self.db.scalars(
            select(Category).where(
                (Category.family_id == family_id) | (Category.family_id.is_(None)),
            )
        ).all()
        for category in categories:
            if category.name.casefold() == normalized_hint:
                return category
        for category in categories:
            if (
                normalized_hint in category.name.casefold()
                or category.name.casefold() in normalized_hint
            ):
                return category
        return None

    def _get_or_create_merchant(self, *, family_id: UUID, name: str) -> Merchant:
        normalized_name = name.casefold()
        merchant = self.db.scalar(
            select(Merchant).where(
                Merchant.family_id == family_id,
                Merchant.normalized_name == normalized_name,
            )
        )
        if merchant is not None:
            return merchant

        merchant = Merchant(
            family_id=family_id,
            name=name,
            normalized_name=normalized_name,
            merchant_type="manual",
        )
        self.db.add(merchant)
        self.db.flush()
        return merchant
