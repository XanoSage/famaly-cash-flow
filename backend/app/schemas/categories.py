from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class SubcategoryResponse(BaseModel):
    id: UUID
    category_id: UUID
    name: str
    translation_key: str | None
    is_system: bool


class CategoryResponse(BaseModel):
    id: UUID
    family_id: UUID | None
    name: str
    translation_key: str | None
    is_system: bool
    subcategories: list[SubcategoryResponse]


class CategoryListResponse(BaseModel):
    rows: list[CategoryResponse]
