from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.service import hash_password, normalize_email
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.account import Account, PaymentInstrument
from app.models.family import Family
from app.models.user import User, UserPreference

E2E_FAMILY_NAME = "E2E Test Household"
E2E_ACCOUNT_NAME = "E2E Main Card"


def seed_e2e_data(db: Session, *, email: str, password: str) -> None:
    normalized_email = normalize_email(email)
    if not normalized_email.endswith("@example.test"):
        raise ValueError("E2E_TEST_EMAIL must use the reserved example.test domain.")
    if len(password) < 12:
        raise ValueError("E2E_TEST_PASSWORD must be at least 12 characters.")

    family = db.scalar(select(Family).where(Family.name == E2E_FAMILY_NAME))
    if family is None:
        family = Family(name=E2E_FAMILY_NAME)
        db.add(family)
        db.flush()

    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is not None and user.family_id != family.id:
        raise ValueError("The E2E email is already assigned to another family.")
    if user is None:
        user = User(
            family=family,
            email=normalized_email,
            password_hash=hash_password(password),
            display_name="E2E Owner",
        )
        db.add(user)
        db.flush()
    else:
        user.password_hash = hash_password(password)
        user.display_name = "E2E Owner"
        user.is_active = True

    account = db.scalar(
        select(Account).where(
            Account.family_id == family.id,
            Account.name == E2E_ACCOUNT_NAME,
        )
    )
    if account is None:
        account = Account(
            family=family,
            owner_user=user,
            type="card",
            name=E2E_ACCOUNT_NAME,
            currency="UAH",
        )
        db.add(account)
        db.flush()
    else:
        account.owner_user = user
        account.type = "card"
        account.currency = "UAH"
        account.is_active = True

    preference = db.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
    if preference is None:
        preference = UserPreference(user=user, default_account=account, language="ru")
        db.add(preference)
    else:
        preference.default_account = account
        preference.language = "ru"

    instrument = db.scalar(
        select(PaymentInstrument).where(
            PaymentInstrument.account_id == account.id,
            PaymentInstrument.masked_label == "E2E card **4242",
        )
    )
    if instrument is None:
        db.add(
            PaymentInstrument(
                account=account,
                type="physical_card",
                masked_label="E2E card **4242",
                last_digits="4242",
            )
        )

    db.commit()


def main() -> None:
    if settings.app_env.lower() not in {"test", "testing"}:
        raise RuntimeError("The E2E seed requires APP_ENV=test.")
    database_name = make_url(settings.database_url).database or ""
    if not database_name.endswith("_e2e"):
        raise RuntimeError("The E2E seed requires a disposable database ending in _e2e.")
    email = os.environ.get("E2E_TEST_EMAIL", "")
    password = os.environ.get("E2E_TEST_PASSWORD", "")
    with SessionLocal() as db:
        seed_e2e_data(db, email=email, password=password)
    print("E2E seed completed (1 synthetic family, user, card account, and payment instrument).")


if __name__ == "__main__":
    main()
