from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at, updated_at, uuid_pk

if TYPE_CHECKING:
    from app.models.family import Family


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("family_id", "name", name="uq_categories_family_id_name"),)

    id: Mapped[uuid_pk]
    family_id: Mapped[UUID | None] = mapped_column(ForeignKey("families.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    translation_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    family: Mapped["Family | None"] = relationship(back_populates="categories")
    subcategories: Mapped[list["Subcategory"]] = relationship(back_populates="category")


class Subcategory(Base):
    __tablename__ = "subcategories"
    __table_args__ = (UniqueConstraint("category_id", "name", name="uq_subcategories_category_id_name"),)

    id: Mapped[uuid_pk]
    category_id: Mapped[UUID] = mapped_column(ForeignKey("categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    translation_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    category: Mapped[Category] = relationship(back_populates="subcategories")
