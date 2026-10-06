from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.auth.authorization import (
    require_family_account,
    require_family_category,
    require_family_merchant,
)
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.account import Account, PaymentInstrument
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transactions import (
    ManualTransactionCreateRequest,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdateRequest,
)
from app.services.transactions import (
    TransactionNotFoundError,
    TransactionService,
    TransactionServiceError,
    TransactionValidationError,
)

router = APIRouter(prefix="/transactions")


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    current_user: User = Depends(get_current_user),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    occurred_from: datetime | None = Query(None),
    occurred_to: datetime | None = Query(None),
    account_id: UUID | None = Query(None),
    payment_instrument_id: UUID | None = Query(None),
    merchant_id: UUID | None = Query(None),
    category_id: UUID | None = Query(None),
    uncategorized: bool | None = Query(None),
    direction: str | None = Query(None),
    transaction_currency: str | None = Query(None, min_length=3, max_length=3),
    flow_type: str | None = Query(None),
    scope: str | None = Query(None),
    needs_review: bool | None = Query(None),
    include_deleted: bool = Query(False),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    family_id = current_user.family_id
    if occurred_from is not None and occurred_to is not None and occurred_from > occurred_to:
        raise HTTPException(status_code=422, detail="occurred_from must be before occurred_to.")
    if account_id is not None:
        require_family_account(db, family_id, account_id)
    if merchant_id is not None:
        require_family_merchant(db, family_id, merchant_id)
    if category_id is not None:
        require_family_category(db, family_id, category_id)
    if payment_instrument_id is not None:
        instrument = db.scalar(
            select(PaymentInstrument)
            .join(PaymentInstrument.account)
            .where(
                PaymentInstrument.id == payment_instrument_id,
                Account.family_id == family_id,
            )
        )
        if instrument is None:
            raise HTTPException(status_code=404, detail="Payment instrument not found.")

    query = select(Transaction).where(Transaction.family_id == family_id)
    query = _apply_filters(
        query,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        account_id=account_id,
        payment_instrument_id=payment_instrument_id,
        merchant_id=merchant_id,
        category_id=category_id,
        uncategorized=uncategorized,
        direction=direction,
        transaction_currency=transaction_currency.upper() if transaction_currency else None,
        flow_type=flow_type,
        scope=scope,
        needs_review=needs_review,
        include_deleted=include_deleted,
    )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.options(
            joinedload(Transaction.account),
            joinedload(Transaction.payment_instrument),
            joinedload(Transaction.merchant),
            joinedload(Transaction.category),
            joinedload(Transaction.subcategory),
        )
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


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: ManualTransactionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionResponse:
    values = payload.model_dump()
    try:
        service = TransactionService(db)
        if payload.direction == "expense":
            if payload.income_type is not None:
                raise TransactionValidationError("An expense cannot have an income type.")
            transaction = service.create_expense(
                user=current_user,
                **{
                    key: value
                    for key, value in values.items()
                    if key not in {"direction", "income_type"}
                },
            )
        else:
            transaction = service.create_income(
                user=current_user,
                **{key: value for key, value in values.items() if key != "direction"},
            )
    except TransactionServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_response(transaction)


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionResponse:
    try:
        transaction = TransactionService(db).get(user=current_user, transaction_id=transaction_id)
    except TransactionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Transaction not found.") from exc
    except TransactionServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_response(transaction)


@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: UUID,
    payload: TransactionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionResponse:
    try:
        transaction = TransactionService(db).update(
            user=current_user,
            transaction_id=transaction_id,
            changes=payload.model_dump(exclude_unset=True),
        )
    except TransactionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Transaction not found.") from exc
    except TransactionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_response(transaction)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        TransactionService(db).soft_delete(user=current_user, transaction_id=transaction_id)
    except TransactionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Transaction not found.") from exc
    except TransactionServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _apply_filters(
    query: Select[tuple[Transaction]],
    *,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    account_id: UUID | None,
    payment_instrument_id: UUID | None,
    merchant_id: UUID | None,
    category_id: UUID | None,
    uncategorized: bool | None,
    direction: str | None,
    transaction_currency: str | None,
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
    if payment_instrument_id is not None:
        query = query.where(Transaction.payment_instrument_id == payment_instrument_id)
    if merchant_id is not None:
        query = query.where(Transaction.merchant_id == merchant_id)
    if category_id is not None:
        query = query.where(Transaction.category_id == category_id)
    if uncategorized is True:
        query = query.where(Transaction.category_id.is_(None))
    elif uncategorized is False:
        query = query.where(Transaction.category_id.is_not(None))
    if direction is not None:
        query = query.where(Transaction.direction == direction)
    if transaction_currency is not None:
        query = query.where(Transaction.transaction_currency == transaction_currency)
    if flow_type is not None:
        query = query.where(Transaction.flow_type == flow_type)
    if scope is not None:
        query = query.where(Transaction.scope == scope)
    if needs_review is not None:
        query = query.where(Transaction.needs_review == needs_review)
    return query


def _to_response(transaction: Transaction) -> TransactionResponse:
    occurred_at = transaction.occurred_at
    if occurred_at.tzinfo is None and transaction.import_batch_id is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    merchant_name = transaction.merchant.name if transaction.merchant else None
    display_description = (
        transaction.description_override
        or merchant_name
        or transaction.description_normalized
        or transaction.description_raw
    )
    return TransactionResponse(
        id=transaction.id,
        family_id=transaction.family_id,
        account_id=transaction.account_id,
        account_name=transaction.account.name if transaction.account else "",
        payment_instrument_id=transaction.payment_instrument_id,
        payment_instrument_label=(
            transaction.payment_instrument.masked_label if transaction.payment_instrument else None
        ),
        owner_user_id=transaction.owner_user_id,
        import_batch_id=transaction.import_batch_id,
        occurred_at=occurred_at,
        amount=transaction.amount,
        currency=transaction.currency,
        transaction_amount=transaction.transaction_amount,
        transaction_currency=transaction.transaction_currency,
        balance_after=transaction.balance_after,
        direction=transaction.direction,
        flow_type=transaction.flow_type,
        transfer_group_id=transaction.transfer_group_id,
        transfer_role=transaction.transfer_role,
        income_type=transaction.income_type,
        scope=transaction.scope,
        description_raw=transaction.description_raw,
        description_normalized=transaction.description_normalized,
        description_override=transaction.description_override,
        display_description=display_description,
        bank_category_raw=transaction.bank_category_raw,
        merchant_id=transaction.merchant_id,
        merchant_name=merchant_name,
        category_id=transaction.category_id,
        category_name=transaction.category.name if transaction.category else None,
        subcategory_id=transaction.subcategory_id,
        subcategory_name=transaction.subcategory.name if transaction.subcategory else None,
        comment=transaction.comment,
        is_cash=transaction.is_cash,
        is_duplicate_candidate=transaction.is_duplicate_candidate,
        needs_review=transaction.needs_review,
    )
