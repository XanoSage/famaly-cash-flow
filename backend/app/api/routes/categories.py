from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.category import Category
from app.models.user import User
from app.schemas.categories import CategoryListResponse, CategoryResponse, SubcategoryResponse

router = APIRouter(prefix="/categories")


@router.get("", response_model=CategoryListResponse)
def list_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CategoryListResponse:
    categories = (
        db.scalars(
            select(Category)
            .options(joinedload(Category.subcategories))
            .where(or_(Category.family_id == current_user.family_id, Category.family_id.is_(None)))
            .order_by(Category.is_system.desc(), Category.name)
        )
        .unique()
        .all()
    )

    return CategoryListResponse(rows=[_to_response(category) for category in categories])


def _to_response(category: Category) -> CategoryResponse:
    return CategoryResponse(
        id=category.id,
        family_id=category.family_id,
        name=category.name,
        translation_key=category.translation_key,
        is_system=category.is_system,
        subcategories=[
            SubcategoryResponse(
                id=subcategory.id,
                category_id=subcategory.category_id,
                name=subcategory.name,
                translation_key=subcategory.translation_key,
                is_system=subcategory.is_system,
            )
            for subcategory in sorted(category.subcategories, key=lambda item: item.name)
        ],
    )
