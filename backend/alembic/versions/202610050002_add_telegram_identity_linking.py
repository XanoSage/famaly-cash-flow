"""add Telegram identity, link tokens, and default accounts

Revision ID: 202610050002
Revises: 202610050001
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610050002"
down_revision: str | None = "202610050001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("default_account_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_user_preferences_default_account_id_accounts",
        "user_preferences",
        "accounts",
        ["default_account_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "telegram_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("private_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_identities")),
        sa.UniqueConstraint("user_id", name="uq_telegram_identities_user_id"),
        sa.UniqueConstraint("telegram_user_id", name="uq_telegram_identities_telegram_user_id"),
    )
    op.alter_column("telegram_identities", "is_active", server_default=None)

    op.create_table(
        "telegram_link_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_link_tokens")),
        sa.UniqueConstraint("token_hash", name="uq_telegram_link_tokens_token_hash"),
    )
    op.create_index("ix_telegram_link_tokens_user_id", "telegram_link_tokens", ["user_id"])
    op.create_index("ix_telegram_link_tokens_expires_at", "telegram_link_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_telegram_link_tokens_expires_at", table_name="telegram_link_tokens")
    op.drop_index("ix_telegram_link_tokens_user_id", table_name="telegram_link_tokens")
    op.drop_table("telegram_link_tokens")
    op.drop_table("telegram_identities")
    op.drop_constraint(
        "fk_user_preferences_default_account_id_accounts",
        "user_preferences",
        type_="foreignkey",
    )
    op.drop_column("user_preferences", "default_account_id")
