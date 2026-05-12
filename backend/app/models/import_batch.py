from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at, updated_at, uuid_pk

if TYPE_CHECKING:
    from app.models.category import Category, Subcategory
    from app.models.family import Family
    from app.models.transaction import Transaction
    from app.models.user import User


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[uuid_pk]
    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), nullable=False)
    uploaded_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    excluded_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    uncategorized_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    work_fop_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    savings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    mapping_version: Mapped[str] = mapped_column(String(40), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    family: Mapped["Family"] = relationship(back_populates="import_batches")
    uploaded_by_user: Mapped["User"] = relationship()
    preview_rows: Mapped[list["ImportPreviewRow"]] = relationship(back_populates="import_batch")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="import_batch")


class ImportPreviewRow(Base):
    __tablename__ = "import_preview_rows"
    __table_args__ = (UniqueConstraint("import_batch_id", "row_number", name="uq_import_preview_rows_batch_id_row_number"),)

    id: Mapped[uuid_pk]
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("import_batches.id"), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    transaction_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    transaction_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    payment_instrument_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bank_category_raw: Mapped[str | None] = mapped_column(String(160), nullable=True)
    description_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    merchant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    proposed_category_id: Mapped[UUID | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    proposed_subcategory_id: Mapped[UUID | None] = mapped_column(ForeignKey("subcategories.id"), nullable=True)
    proposed_flow_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proposed_scope: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    duplicate_transaction_id: Mapped[UUID | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    import_batch: Mapped["ImportBatch"] = relationship(back_populates="preview_rows")
    proposed_category: Mapped["Category | None"] = relationship(foreign_keys=[proposed_category_id])
    proposed_subcategory: Mapped["Subcategory | None"] = relationship(foreign_keys=[proposed_subcategory_id])
    duplicate_transaction: Mapped["Transaction | None"] = relationship(foreign_keys=[duplicate_transaction_id])
