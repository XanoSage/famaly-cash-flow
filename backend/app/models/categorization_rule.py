from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at, updated_at, uuid_pk

if TYPE_CHECKING:
    from app.models.category import Category, Subcategory
    from app.models.family import Family
    from app.models.merchant import Merchant


class CategorizationRule(Base):
    __tablename__ = "categorization_rules"

    id: Mapped[uuid_pk]
    family_id: Mapped[UUID | None] = mapped_column(ForeignKey("families.id"), nullable=True)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    pattern: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bank_category: Mapped[str | None] = mapped_column(String(160), nullable=True)
    merchant_id: Mapped[UUID | None] = mapped_column(ForeignKey("merchants.id"), nullable=True)
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    subcategory_id: Mapped[UUID | None] = mapped_column(ForeignKey("subcategories.id"), nullable=True)
    flow_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scope: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    family: Mapped["Family | None"] = relationship()
    merchant: Mapped["Merchant | None"] = relationship()
    category: Mapped["Category | None"] = relationship()
    subcategory: Mapped["Subcategory | None"] = relationship()
