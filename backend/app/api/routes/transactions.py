from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.transaction import Transaction
from app.schemas.transactions import TransactionListResponse, TransactionResponse

router = APIRouter(prefix="/transactions")


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    family_id: UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    occurred_from: datetime | None = Query(None),
    occurred_to: datetime | None = Query(None),
    account_id: UUID | None = Query(None),
    merchant_id: UUID | None = Query(None),
    category_id: UUID | None = Query(None),
    flow_type: str | None = Query(None),
    scope: str | None = Query(None),
    needs_review: bool | None = Query(None),
    include_deleted: bool = Query(False),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    query = select(Transaction).where(Transaction.family_id == family_id)
    query = _apply_filters(
        query,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        account_id=account_id,
        merchant_id=merchant_id,
        category_id=category_id,
        flow_type=flow_type,
        scope=scope,
        needs_review=needs_review,
        include_deleted=include_deleted,
    )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.options(joinedload(Transaction.merchant))
        .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return TransactionListResponse(
        total=total,
        offset=offset,
        limit=limit,
        rows=[_to_response(row) for row in rows],
    )


def _apply_filters(
    query: Select[tuple[Transaction]],
    *,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    account_id: UUID | None,
    merchant_id: UUID | None,
    category_id: UUID | None,
    flow_type: str | None,
    scope: str | None,
    needs_review: bool | None,
    include_deleted: bool,
) -> Select[tuple[Transaction]]:
    if not include_deleted:
        query = query.where(Transaction.deleted_at.is_(None))
    if occurred_from is not None:
        query = query.where(Transaction.occurred_at >= occurred_from)
    if occurred_to is not None:
        query = query.where(Transaction.occurred_at <= occurred_to)
    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)
    if merchant_id is not None:
        query = query.where(Transaction.merchant_id == merchant_id)
    if category_id is not None:
        query = query.where(Transaction.category_id == category_id)
    if flow_type is not None:
        query = query.where(Transaction.flow_type == flow_type)
    if scope is not None:
        query = query.where(Transaction.scope == scope)
    if needs_review is not None:
        query = query.where(Transaction.needs_review == needs_review)
    return query


def _to_response(transaction: Transaction) -> TransactionResponse:
    return TransactionResponse(
        id=transaction.id,
        family_id=transaction.family_id,
        account_id=transaction.account_id,
        payment_instrument_id=transaction.payment_instrument_id,
        owner_user_id=transaction.owner_user_id,
        import_batch_id=transaction.import_batch_id,
        occurred_at=transaction.occurred_at,
        amount=transaction.amount,
        currency=transaction.currency,
        transaction_amount=transaction.transaction_amount,
        transaction_currency=transaction.transaction_currency,
        balance_after=transaction.balance_after,
        direction=transaction.direction,
        flow_type=transaction.flow_type,
        income_type=transaction.income_type,
        scope=transaction.scope,
        description_raw=transaction.description_raw,
        description_normalized=transaction.description_normalized,
        bank_category_raw=transaction.bank_category_raw,
        merchant_id=transaction.merchant_id,
        merchant_name=transaction.merchant.name if transaction.merchant else None,
        category_id=transaction.category_id,
        subcategory_id=transaction.subcategory_id,
        comment=transaction.comment,
        is_cash=transaction.is_cash,
        is_duplicate_candidate=transaction.is_duplicate_candidate,
        needs_review=transaction.needs_review,
    )
