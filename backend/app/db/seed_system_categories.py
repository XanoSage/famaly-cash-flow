from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.system_categories import SYSTEM_CATEGORY_TREE, make_translation_key
from app.models.category import Category, Subcategory


def seed_system_categories(db: Session) -> None:
    for category_name, subcategory_names in SYSTEM_CATEGORY_TREE.items():
        category = db.scalar(
            select(Category).where(
                Category.family_id.is_(None),
                Category.name == category_name,
                Category.is_system.is_(True),
            )
        )
        if category is None:
            category = Category(
                family_id=None,
                name=category_name,
                translation_key=make_translation_key(category_name),
                is_system=True,
            )
            db.add(category)
            db.flush()

        for subcategory_name in subcategory_names:
            subcategory = db.scalar(
                select(Subcategory).where(
                    Subcategory.category_id == category.id,
                    Subcategory.name == subcategory_name,
                    Subcategory.is_system.is_(True),
                )
            )
            if subcategory is None:
                db.add(
                    Subcategory(
                        category_id=category.id,
                        name=subcategory_name,
                        translation_key=make_translation_key(category_name, subcategory_name),
                        is_system=True,
                    )
                )

    db.commit()


def main() -> None:
    with SessionLocal() as db:
        seed_system_categories(db)


if __name__ == "__main__":
    main()

