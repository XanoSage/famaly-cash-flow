from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at, updated_at, uuid_pk

if TYPE_CHECKING:
    from app.models.family import Family


class Merchant(Base):
    __tablename__ = "merchants"
    __table_args__ = (
        UniqueConstraint("family_id", "normalized_name", name="uq_merchants_family_id_normalized_name"),
    )

    id: Mapped[uuid_pk]
    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    merchant_type: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    family: Mapped["Family"] = relationship(back_populates="merchants")
