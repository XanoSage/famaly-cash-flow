from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.cash import (
    CashExpenseCreateRequest,
    CashOperationResponse,
    CashSummaryResponse,
    CashWalletResponse,
    CashWithdrawalCreateRequest,
    CashWithdrawalResponse,
)
from app.services.transactions import (
    TransactionNotFoundError,
    TransactionService,
    TransactionServiceError,
)

router = APIRouter(prefix="/cash")


@router.get("/summary", response_model=CashSummaryResponse)
def cash_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CashSummaryResponse:
    service = TransactionService(db)
    wallet = service.get_cash_wallet(user=current_user)
    if wallet is None:
        return CashSummaryResponse(
            wallet=None,
            balance=Decimal("0.00"),
            recent_operations=[],
        )

    transactions = db.scalars(
        select(Transaction)
        .options(joinedload(Transaction.merchant))
        .where(
            Transaction.family_id == current_user.family_id,
            Transaction.account_id == wallet.id,
            Transaction.deleted_at.is_(None),
        )
        .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
        .limit(15)
    ).all()
    return CashSummaryResponse(
        wallet=CashWalletResponse(id=wallet.id, name=wallet.name, currency=wallet.currency),
        balance=service.cash_wallet_balance(user=current_user),
        recent_operations=[_cash_operation(transaction) for transaction in transactions],
    )


@router.post("/expenses", response_model=CashOperationResponse, status_code=status.HTTP_201_CREATED)
def create_cash_expense(
    payload: CashExpenseCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CashOperationResponse:
    try:
        transaction = TransactionService(db).create_cash_expense(
            user=current_user,
            **payload.model_dump(),
        )
    except TransactionServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _cash_operation(transaction)


@router.post(
    "/transfers", response_model=CashWithdrawalResponse, status_code=status.HTTP_201_CREATED
)
def create_cash_withdrawal(
    payload: CashWithdrawalCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CashWithdrawalResponse:
    try:
        source, destination = TransactionService(db).create_cash_withdrawal(
            user=current_user,
            **payload.model_dump(),
        )
    except TransactionServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    service = TransactionService(db)
    return CashWithdrawalResponse(
        transfer_group_id=source.transfer_group_id,
        source_transaction_id=source.id,
        destination_transaction_id=destination.id,
        amount=abs(source.amount),
        cash_balance=service.cash_wallet_balance(user=current_user),
    )


@router.post(
    "/imported-withdrawals/{transaction_id}/link",
    response_model=CashWithdrawalResponse,
    status_code=status.HTTP_201_CREATED,
)
def link_imported_cash_withdrawal(
    transaction_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CashWithdrawalResponse:
    service = TransactionService(db)
    try:
        source, destination = service.link_imported_cash_withdrawal(
            user=current_user,
            transaction_id=transaction_id,
        )
    except TransactionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Transaction not found.") from exc
    except TransactionServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CashWithdrawalResponse(
        transfer_group_id=source.transfer_group_id,
        source_transaction_id=source.id,
        destination_transaction_id=destination.id,
        amount=abs(source.amount),
        cash_balance=service.cash_wallet_balance(user=current_user),
    )


def _cash_operation(transaction: Transaction) -> CashOperationResponse:
    merchant_name = transaction.merchant.name if transaction.merchant else None
    description = (
        transaction.description_override
        or merchant_name
        or transaction.description_normalized
        or transaction.description_raw
    )
    return CashOperationResponse(
        id=transaction.id,
        occurred_at=transaction.occurred_at,
        amount=transaction.amount,
        currency=transaction.currency,
        direction=transaction.direction,
        flow_type=transaction.flow_type,
        description=description,
        transfer_group_id=transaction.transfer_group_id,
        transfer_role=transaction.transfer_role,
    )
