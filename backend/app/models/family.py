from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at, updated_at, uuid_pk

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.category import Category
    from app.models.merchant import Merchant
    from app.models.user import User


class Family(Base):
    __tablename__ = "families"

    id: Mapped[uuid_pk]
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    users: Mapped[list["User"]] = relationship(back_populates="family")
    accounts: Mapped[list["Account"]] = relationship(back_populates="family")
    categories: Mapped[list["Category"]] = relationship(back_populates="family")
    merchants: Mapped[list["Merchant"]] = relationship(back_populates="family")
