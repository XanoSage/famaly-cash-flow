from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app import models  # noqa: F401
from app.db.base import Base


@pytest.fixture(scope="session")
def postgres_engine() -> Iterator[Engine]:
    enabled = os.getenv("RUN_POSTGRES_INTEGRATION") == "1"
    required = os.getenv("POSTGRES_INTEGRATION_REQUIRED") == "1"
    database_url = os.getenv("POSTGRES_INTEGRATION_DATABASE_URL")
    if not enabled or not database_url:
        message = "Set RUN_POSTGRES_INTEGRATION=1 and POSTGRES_INTEGRATION_DATABASE_URL."
        if required:
            raise pytest.UsageError(message)
        pytest.skip(message)

    url = make_url(database_url)
    if not url.drivername.startswith("postgresql"):
        raise pytest.UsageError("PostgreSQL integration tests require a PostgreSQL URL.")
    if not (url.database or "").endswith("_integration_test"):
        raise pytest.UsageError(
            "PostgreSQL integration tests require a database ending in '_integration_test'."
        )

    engine = create_engine(
        url,
        poolclass=NullPool,
        connect_args={"connect_timeout": 5},
    )
    backend_root = Path(__file__).resolve().parents[2]
    alembic_config = Config(str(backend_root / "alembic.ini"))
    heads = ScriptDirectory.from_config(alembic_config).get_heads()
    if len(heads) != 1:
        engine.dispose()
        raise pytest.UsageError("PostgreSQL integration tests require exactly one Alembic head.")

    try:
        with engine.connect() as connection:
            database_name = connection.scalar(text("SELECT current_database()"))
            versions = connection.scalars(text("SELECT version_num FROM alembic_version")).all()
    except Exception:
        engine.dispose()
        raise pytest.UsageError(
            "Could not connect to or inspect the dedicated PostgreSQL integration database."
        ) from None
    if database_name != url.database:
        engine.dispose()
        raise pytest.UsageError("Connected PostgreSQL database did not match the configured URL.")
    if versions != heads:
        engine.dispose()
        raise pytest.UsageError("Run Alembic upgrade head before PostgreSQL integration tests.")

    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def postgres_session_factory(postgres_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=postgres_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def empty_postgres_database(postgres_engine: Engine) -> Iterator[None]:
    table_names = [f'"{table.name}"' for table in Base.metadata.sorted_tables]
    if table_names:
        with postgres_engine.begin() as connection:
            connection.execute(
                text(f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE")
            )
    yield
