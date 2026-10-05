from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.category import Category
from app.models.transaction import Transaction


class TransactionReviewError(ValueError):
    pass


class TransactionNotFoundError(TransactionReviewError):
    pass


class CategoryNotFoundError(TransactionReviewError):
    pass


class _Unset:
    pass


UNSET: Final = _Unset()


class TransactionReviewService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_pending(self, *, family_id: UUID, limit: int = 5) -> list[Transaction]:
        return self.db.scalars(
            select(Transaction)
            .options(joinedload(Transaction.merchant), joinedload(Transaction.category))
            .where(
                Transaction.family_id == family_id,
                Transaction.deleted_at.is_(None),
                Transaction.needs_review.is_(True),
            )
            .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
            .limit(limit)
        ).all()

    def get_for_review(self, *, family_id: UUID, transaction_id: UUID) -> Transaction:
        return self._get_transaction(family_id=family_id, transaction_id=transaction_id)

    def update(
        self,
        *,
        family_id: UUID,
        transaction_id: UUID,
        category_id: UUID | None | _Unset = UNSET,
        comment: str | None | _Unset = UNSET,
        needs_review: bool | None | _Unset = UNSET,
    ) -> Transaction:
        transaction = self._get_transaction(family_id=family_id, transaction_id=transaction_id)

        if not isinstance(category_id, _Unset):
            if category_id is None:
                transaction.category = None
            else:
                category = self.db.scalar(
                    select(Category).where(
                        Category.id == category_id,
                        or_(Category.family_id == family_id, Category.family_id.is_(None)),
                    )
                )
                if category is None:
                    raise CategoryNotFoundError("Category not found.")
                transaction.category = category

        if not isinstance(comment, _Unset):
            transaction.comment = comment
        if not isinstance(needs_review, _Unset) and needs_review is not None:
            transaction.needs_review = needs_review

        self.db.commit()
        self.db.refresh(transaction)
        return transaction

    def mark_reviewed(self, *, family_id: UUID, transaction_id: UUID) -> bool:
        transaction = self._get_transaction(family_id=family_id, transaction_id=transaction_id)
        if not transaction.needs_review:
            return False
        transaction.needs_review = False
        self.db.commit()
        return True

    def assign_category(
        self,
        *,
        family_id: UUID,
        transaction_id: UUID,
        category_id: UUID,
    ) -> Transaction:
        return self.update(
            family_id=family_id,
            transaction_id=transaction_id,
            category_id=category_id,
            needs_review=False,
        )

    def _get_transaction(self, *, family_id: UUID, transaction_id: UUID) -> Transaction:
        transaction = self.db.scalar(
            select(Transaction)
            .options(joinedload(Transaction.category))
            .where(
                Transaction.id == transaction_id,
                Transaction.family_id == family_id,
                Transaction.deleted_at.is_(None),
            )
        )
        if transaction is None:
            raise TransactionNotFoundError("Transaction not found.")
        return transaction
