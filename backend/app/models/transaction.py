from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at, updated_at, uuid_pk

if TYPE_CHECKING:
    from app.models.account import Account, PaymentInstrument
    from app.models.category import Category, Subcategory
    from app.models.family import Family
    from app.models.import_batch import ImportBatch
    from app.models.merchant import Merchant
    from app.models.user import User


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("family_id", "bank_transaction_id", name="uq_transactions_family_id_bank_transaction_id"),
    )

    id: Mapped[uuid_pk]
    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), nullable=False)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    payment_instrument_id: Mapped[UUID | None] = mapped_column(ForeignKey("payment_instruments.id"), nullable=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    import_batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("import_batches.id"), nullable=True)
    bank_transaction_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="UAH", nullable=False)
    transaction_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    transaction_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    flow_type: Mapped[str] = mapped_column(String(64), nullable=False)
    income_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scope: Mapped[str] = mapped_column(String(64), default="family", nullable=False)
    description_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_category_raw: Mapped[str | None] = mapped_column(String(160), nullable=True)
    merchant_id: Mapped[UUID | None] = mapped_column(ForeignKey("merchants.id"), nullable=True)
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    subcategory_id: Mapped[UUID | None] = mapped_column(ForeignKey("subcategories.id"), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_cash: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_duplicate_candidate: Mapped[bool] = mapped_column(default=False, nullable=False)
    needs_review: Mapped[bool] = mapped_column(default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    family: Mapped["Family"] = relationship(back_populates="transactions")
    account: Mapped["Account"] = relationship()
    payment_instrument: Mapped["PaymentInstrument | None"] = relationship()
    owner_user: Mapped["User | None"] = relationship(foreign_keys=[owner_user_id])
    import_batch: Mapped["ImportBatch | None"] = relationship(back_populates="transactions")
    merchant: Mapped["Merchant | None"] = relationship()
    category: Mapped["Category | None"] = relationship()
    subcategory: Mapped["Subcategory | None"] = relationship()
    deleted_by_user: Mapped["User | None"] = relationship(foreign_keys=[deleted_by_user_id])
