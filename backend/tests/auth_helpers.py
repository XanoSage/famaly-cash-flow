from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def current_test_user_dependency(db_session: Session):
    def get_test_user() -> User:
        user = db_session.scalar(select(User).order_by(User.id).limit(1))
        if user is None:
            raise AssertionError("This API test must seed an authenticated user.")
        return user

    return get_test_user
