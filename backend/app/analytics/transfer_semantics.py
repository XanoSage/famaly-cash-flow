from __future__ import annotations

from uuid import UUID

from app.models.transaction import Transaction

TRANSFER_FLOW_TYPES = frozenset(
    {
        "cash_withdrawal",
        "transfer_to_own_account",
        "transfer_to_savings",
        "transfer_to_wife",
        "person_transfer",
    }
)


def counts_as_transfer_metric(
    transaction: Transaction,
    *,
    account_filter: UUID | None,
) -> bool:
    """Count withdrawals once family-wide, or once in a selected account view."""
    if transaction.flow_type != "cash_withdrawal":
        return True
    if account_filter is not None:
        return transaction.account_id == account_filter
    return transaction.transfer_role in {None, "source"}
