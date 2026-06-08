from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import pytest

from app import models  # noqa: F401
from app.db.base import Base
from app.db.seed_demo_dashboard import DEMO_FAMILY_NAME, seed_demo_dashboard
from app.models.family import Family
from app.models.transaction import Transaction


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session


def test_seed_demo_dashboard_creates_demo_data_once(db_session: Session) -> None:
    first = seed_demo_dashboard(db_session)
    second = seed_demo_dashboard(db_session)

    assert first.family_id == second.family_id
    assert first.account_id == second.account_id
    assert first.transaction_count == 10
    assert second.transaction_count == 10

    family = db_session.scalar(select(Family).where(Family.name == DEMO_FAMILY_NAME))
    assert family is not None

    transactions = db_session.scalars(
        select(Transaction).where(Transaction.family_id == family.id)
    ).all()
    assert len(transactions) == 10
    assert any(item.scope == "work_fop" for item in transactions)
    assert any(item.flow_type == "transfer_to_savings" for item in transactions)
    assert any(item.needs_review for item in transactions)
