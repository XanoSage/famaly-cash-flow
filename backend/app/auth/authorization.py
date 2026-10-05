from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.category import Category
from app.models.merchant import Merchant
from app.models.user import User


def require_family_account(db: Session, family_id: UUID, account_id: UUID) -> Account:
    account = db.scalar(
        select(Account).where(Account.id == account_id, Account.family_id == family_id)
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    if account.owner_user_id is not None:
        owner_is_in_family = db.scalar(
            select(User.id).where(
                User.id == account.owner_user_id,
                User.family_id == family_id,
            )
        )
        if owner_is_in_family is None:
            raise HTTPException(status_code=404, detail="Account not found.")
    return account


def require_family_category(
    db: Session,
    family_id: UUID,
    category_id: UUID,
    *,
    allow_system: bool = True,
) -> Category:
    family_filter = Category.family_id == family_id
    if allow_system:
        family_filter = or_(family_filter, Category.family_id.is_(None))
    category = db.scalar(select(Category).where(Category.id == category_id, family_filter))
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found.")
    return category


def require_family_merchant(db: Session, family_id: UUID, merchant_id: UUID) -> Merchant:
    merchant = db.scalar(
        select(Merchant).where(Merchant.id == merchant_id, Merchant.family_id == family_id)
    )
    if merchant is None:
        raise HTTPException(status_code=404, detail="Merchant not found.")
    return merchant


def validate_analytics_entities(
    db: Session,
    family_id: UUID,
    *,
    account_id: UUID | None,
    category_id: UUID | None = None,
) -> None:
    if account_id is not None:
        require_family_account(db, family_id, account_id)
    if category_id is not None:
        require_family_category(db, family_id, category_id)
