"""add global user email identity and persistent auth sessions

Revision ID: 202610050001
Revises: 202605120002
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610050001"
down_revision: str | None = "202605120002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM users
                GROUP BY lower(regexp_replace(email, '^[[:space:]]+|[[:space:]]+$', '', 'g'))
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot normalize user emails: duplicate case-insensitive addresses exist';
            END IF;
        END
        $$;
        """
    )
    op.drop_constraint("uq_users_family_id_email", "users", type_="unique")
    op.drop_index("ix_users_email", table_name="users")
    op.execute(
        "UPDATE users SET email = lower(regexp_replace(email, '^[[:space:]]+|[[:space:]]+$', '', 'g'))"
    )
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.alter_column("users", "is_active", server_default=None)
    op.create_unique_constraint("uq_users_email", "users", ["email"])

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("refresh_token_hash", name="uq_auth_sessions_refresh_token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "is_active")
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_unique_constraint("uq_users_family_id_email", "users", ["family_id", "email"])
