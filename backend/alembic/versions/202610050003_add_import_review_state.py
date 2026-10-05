"""persist import review decisions

Revision ID: 202610050003
Revises: 202610050002
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610050003"
down_revision: str | None = "202610050002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_batches",
        sa.Column("auto_ready_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "import_batches",
        sa.Column("needs_review_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.alter_column("import_batches", "auto_ready_count", server_default=None)
    op.alter_column("import_batches", "needs_review_count", server_default=None)

    op.add_column(
        "import_preview_rows",
        sa.Column("duplicate_included", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "import_preview_rows",
        sa.Column(
            "reviewed_uncategorized", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.add_column(
        "import_preview_rows",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("import_preview_rows", "duplicate_included", server_default=None)
    op.alter_column("import_preview_rows", "reviewed_uncategorized", server_default=None)


def downgrade() -> None:
    op.drop_column("import_preview_rows", "reviewed_at")
    op.drop_column("import_preview_rows", "reviewed_uncategorized")
    op.drop_column("import_preview_rows", "duplicate_included")
    op.drop_column("import_batches", "needs_review_count")
    op.drop_column("import_batches", "auto_ready_count")
