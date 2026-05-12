from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at, updated_at, uuid_pk

if TYPE_CHECKING:
    from app.models.family import Family
    from app.models.user import User


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid_pk]
    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="UAH", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    family: Mapped["Family"] = relationship(back_populates="accounts")
    owner_user: Mapped["User | None"] = relationship()
    payment_instruments: Mapped[list["PaymentInstrument"]] = relationship(back_populates="account")


class PaymentInstrument(Base):
    __tablename__ = "payment_instruments"
    __table_args__ = (
        UniqueConstraint("account_id", "masked_label", name="uq_payment_instruments_account_id_masked_label"),
    )

    id: Mapped[uuid_pk]
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    masked_label: Mapped[str] = mapped_column(String(64), nullable=False)
    last_digits: Mapped[str | None] = mapped_column(String(4), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    account: Mapped[Account] = relationship(back_populates="payment_instruments")
