from app import models  # noqa: F401
from app.db.base import Base
from sqlalchemy.orm import configure_mappers


def test_database_relationships_are_configurable() -> None:
    configure_mappers()


def test_import_and_transaction_tables_are_registered() -> None:
    tables = Base.metadata.tables

    assert "import_batches" in tables
    assert "import_preview_rows" in tables
    assert "transactions" in tables


def test_transaction_table_has_analytics_foreign_keys() -> None:
    transaction_columns = Base.metadata.tables["transactions"].columns

    assert "family_id" in transaction_columns
    assert "account_id" in transaction_columns
    assert "merchant_id" in transaction_columns
    assert "category_id" in transaction_columns
    assert "subcategory_id" in transaction_columns
    assert "import_batch_id" in transaction_columns
