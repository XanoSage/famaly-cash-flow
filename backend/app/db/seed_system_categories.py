from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.system_categories import (
    SYSTEM_BANK_CATEGORY_MAPPINGS,
    SYSTEM_CATEGORY_TREE,
    make_translation_key,
)
from app.models.categorization_rule import CategorizationRule
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

    for bank_category, (category_name, subcategory_name) in SYSTEM_BANK_CATEGORY_MAPPINGS.items():
        category = db.scalar(
            select(Category).where(
                Category.family_id.is_(None),
                Category.name == category_name,
                Category.is_system.is_(True),
            )
        )
        if category is None:
            raise RuntimeError(f"System category {category_name!r} must be seeded before its rule.")
        subcategory = db.scalar(
            select(Subcategory).where(
                Subcategory.category_id == category.id,
                Subcategory.name == subcategory_name,
                Subcategory.is_system.is_(True),
            )
        )
        if subcategory is None:
            raise RuntimeError(
                f"System subcategory {category_name!r} / {subcategory_name!r} must be seeded first."
            )
        rule = db.scalar(
            select(CategorizationRule).where(
                CategorizationRule.family_id.is_(None),
                CategorizationRule.rule_type == "bank_category",
                CategorizationRule.bank_category == bank_category,
            )
        )
        if rule is None:
            rule = CategorizationRule(
                family_id=None,
                rule_type="bank_category",
                bank_category=bank_category,
                priority=100,
                is_active=True,
            )
            db.add(rule)
        rule.category_id = category.id
        rule.subcategory_id = subcategory.id
        rule.priority = 100
        rule.is_active = True

    db.commit()


def main() -> None:
    with SessionLocal() as db:
        seed_system_categories(db)


if __name__ == "__main__":
    main()
