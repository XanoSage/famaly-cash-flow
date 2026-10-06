"""add cash wallet and linked withdrawal legs

Revision ID: 202610060002
Revises: 202610060001
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610060002"
down_revision: str | None = "202610060001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_accounts_family_active_cash_wallet",
        "accounts",
        ["family_id"],
        unique=True,
        postgresql_where=sa.text("type = 'cash' AND is_active = true"),
    )
    op.add_column("transactions", sa.Column("transfer_group_id", sa.Uuid(), nullable=True))
    op.add_column("transactions", sa.Column("transfer_role", sa.String(length=16), nullable=True))
    op.create_unique_constraint(
        "uq_transactions_transfer_group_role",
        "transactions",
        ["transfer_group_id", "transfer_role"],
    )
    op.create_check_constraint(
        op.f("ck_transactions_cash_withdrawal_transfer_link_valid"),
        "transactions",
        "(transfer_group_id IS NULL AND transfer_role IS NULL) OR "
        "(transfer_group_id IS NOT NULL AND direction = 'transfer' "
        "AND flow_type = 'cash_withdrawal' AND "
        "((transfer_role = 'source' AND amount < 0) OR "
        "(transfer_role = 'destination' AND amount > 0)))",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_transactions_cash_withdrawal_transfer_link_valid"),
        "transactions",
        type_="check",
    )
    op.drop_constraint("uq_transactions_transfer_group_role", "transactions", type_="unique")
    op.drop_column("transactions", "transfer_role")
    op.drop_column("transactions", "transfer_group_id")
    op.drop_index("uq_accounts_family_active_cash_wallet", table_name="accounts")
