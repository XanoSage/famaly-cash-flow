"""create import and transaction tables

Revision ID: 202605120002
Revises: 202605120001
Create Date: 2026-05-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202605120002"
down_revision: str | None = "202605120001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("excluded_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("uncategorized_count", sa.Integer(), nullable=False),
        sa.Column("work_fop_count", sa.Integer(), nullable=False),
        sa.Column("savings_count", sa.Integer(), nullable=False),
        sa.Column("parser_version", sa.String(length=40), nullable=False),
        sa.Column("mapping_version", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], name=op.f("fk_import_batches_family_id_families")),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            name=op.f("fk_import_batches_uploaded_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batches")),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("payment_instrument_id", sa.Uuid(), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("import_batch_id", sa.Uuid(), nullable=True),
        sa.Column("bank_transaction_id", sa.String(length=120), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("transaction_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("transaction_currency", sa.String(length=3), nullable=True),
        sa.Column("balance_after", sa.Numeric(14, 2), nullable=True),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("flow_type", sa.String(length=64), nullable=False),
        sa.Column("income_type", sa.String(length=32), nullable=True),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("description_raw", sa.Text(), nullable=True),
        sa.Column("description_normalized", sa.Text(), nullable=True),
        sa.Column("bank_category_raw", sa.String(length=160), nullable=True),
        sa.Column("merchant_id", sa.Uuid(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("subcategory_id", sa.Uuid(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("is_cash", sa.Boolean(), nullable=False),
        sa.Column("is_duplicate_candidate", sa.Boolean(), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name=op.f("fk_transactions_account_id_accounts")),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name=op.f("fk_transactions_category_id_categories")),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"],
            ["users.id"],
            name=op.f("fk_transactions_deleted_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], name=op.f("fk_transactions_family_id_families")),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batches.id"],
            name=op.f("fk_transactions_import_batch_id_import_batches"),
        ),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], name=op.f("fk_transactions_merchant_id_merchants")),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_transactions_owner_user_id_users")),
        sa.ForeignKeyConstraint(
            ["payment_instrument_id"],
            ["payment_instruments.id"],
            name=op.f("fk_transactions_payment_instrument_id_payment_instruments"),
        ),
        sa.ForeignKeyConstraint(
            ["subcategory_id"],
            ["subcategories.id"],
            name=op.f("fk_transactions_subcategory_id_subcategories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
        sa.UniqueConstraint("family_id", "bank_transaction_id", name="uq_transactions_family_id_bank_transaction_id"),
    )
    op.create_index("ix_transactions_family_id_occurred_at", "transactions", ["family_id", "occurred_at"])
    op.create_index("ix_transactions_family_id_category_id", "transactions", ["family_id", "category_id"])
    op.create_index("ix_transactions_family_id_merchant_id", "transactions", ["family_id", "merchant_id"])
    op.create_table(
        "import_preview_rows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("transaction_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("transaction_currency", sa.String(length=3), nullable=True),
        sa.Column("balance_after", sa.Numeric(14, 2), nullable=True),
        sa.Column("payment_instrument_label", sa.String(length=120), nullable=True),
        sa.Column("bank_category_raw", sa.String(length=160), nullable=True),
        sa.Column("description_raw", sa.Text(), nullable=True),
        sa.Column("merchant_name", sa.String(length=255), nullable=True),
        sa.Column("proposed_category_id", sa.Uuid(), nullable=True),
        sa.Column("proposed_subcategory_id", sa.Uuid(), nullable=True),
        sa.Column("proposed_flow_type", sa.String(length=64), nullable=True),
        sa.Column("proposed_scope", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("duplicate_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("normalized_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["duplicate_transaction_id"],
            ["transactions.id"],
            name=op.f("fk_import_preview_rows_duplicate_transaction_id_transactions"),
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batches.id"],
            name=op.f("fk_import_preview_rows_import_batch_id_import_batches"),
        ),
        sa.ForeignKeyConstraint(
            ["proposed_category_id"],
            ["categories.id"],
            name=op.f("fk_import_preview_rows_proposed_category_id_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["proposed_subcategory_id"],
            ["subcategories.id"],
            name=op.f("fk_import_preview_rows_proposed_subcategory_id_subcategories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_preview_rows")),
        sa.UniqueConstraint("import_batch_id", "row_number", name="uq_import_preview_rows_batch_id_row_number"),
    )
    op.create_index(
        "ix_import_preview_rows_batch_id_status",
        "import_preview_rows",
        ["import_batch_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_import_preview_rows_batch_id_status", table_name="import_preview_rows")
    op.drop_table("import_preview_rows")
    op.drop_index("ix_transactions_family_id_merchant_id", table_name="transactions")
    op.drop_index("ix_transactions_family_id_category_id", table_name="transactions")
    op.drop_index("ix_transactions_family_id_occurred_at", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("import_batches")
