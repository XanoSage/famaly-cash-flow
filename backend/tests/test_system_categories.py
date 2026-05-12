from app.db.system_categories import SYSTEM_CATEGORY_TREE


def test_system_category_tree_contains_core_categories() -> None:
    assert "Еда" in SYSTEM_CATEGORY_TREE
    assert "Дети" in SYSTEM_CATEGORY_TREE
    assert "Накопления" in SYSTEM_CATEGORY_TREE
    assert "Супермаркеты" in SYSTEM_CATEGORY_TREE["Еда"]
    assert "Школа" in SYSTEM_CATEGORY_TREE["Дети"]
    assert "Скарбничка" in SYSTEM_CATEGORY_TREE["Накопления"]

