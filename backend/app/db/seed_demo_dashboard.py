from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.account import Account, PaymentInstrument
from app.models.category import Category
from app.models.family import Family
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.models.user import User

DEMO_FAMILY_NAME = "Demo Family Cash Flow"
DEMO_OWNER_EMAIL = "demo-owner@example.local"


@dataclass(frozen=True)
class DemoSeedResult:
    family_id: str
    account_id: str
    transaction_count: int


def seed_demo_dashboard(db: Session) -> DemoSeedResult:
    family = _get_or_create_family(db)
    owner = _get_or_create_owner(db, family)
    account = _get_or_create_account(db, family, owner)
    _get_or_create_payment_instrument(db, account)

    categories = {
        "Еда": _get_or_create_category(db, family, "Еда"),
        "Здоровье": _get_or_create_category(db, family, "Здоровье"),
        "Дети": _get_or_create_category(db, family, "Дети"),
        "Рабочее/FOP": _get_or_create_category(db, family, "Рабочее/FOP"),
    }
    merchants = {
        "Silpo": _get_or_create_merchant(db, family, "Silpo", "store"),
        "АТБ": _get_or_create_merchant(db, family, "АТБ", "store"),
        "Аптека": _get_or_create_merchant(db, family, "Аптека", "store"),
        "Школа": _get_or_create_merchant(db, family, "Школа", "education"),
        "OpenAI": _get_or_create_merchant(db, family, "OpenAI", "service"),
    }

    for item in _demo_transactions(categories, merchants):
        _get_or_create_transaction(db, family, account, item)

    db.commit()
    transaction_count = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.family_id == family.id)
    )
    return DemoSeedResult(
        family_id=str(family.id),
        account_id=str(account.id),
        transaction_count=transaction_count or 0,
    )


def _get_or_create_family(db: Session) -> Family:
    family = db.scalar(select(Family).where(Family.name == DEMO_FAMILY_NAME))
    if family is not None:
        return family
    family = Family(name=DEMO_FAMILY_NAME)
    db.add(family)
    db.flush()
    return family


def _get_or_create_owner(db: Session, family: Family) -> User:
    owner = db.scalar(
        select(User).where(
            User.family_id == family.id,
            User.email == DEMO_OWNER_EMAIL,
        )
    )
    if owner is not None:
        return owner
    owner = User(
        family=family,
        email=DEMO_OWNER_EMAIL,
        password_hash="demo-not-for-login",
        display_name="Demo Owner",
    )
    db.add(owner)
    db.flush()
    return owner


def _get_or_create_account(db: Session, family: Family, owner: User) -> Account:
    account = db.scalar(
        select(Account).where(
            Account.family_id == family.id,
            Account.name == "Demo main card",
        )
    )
    if account is not None:
        return account
    account = Account(
        family=family,
        owner_user=owner,
        type="card",
        name="Demo main card",
        currency="UAH",
    )
    db.add(account)
    db.flush()
    return account


def _get_or_create_payment_instrument(db: Session, account: Account) -> PaymentInstrument:
    instrument = db.scalar(
        select(PaymentInstrument).where(
            PaymentInstrument.account_id == account.id,
            PaymentInstrument.masked_label == "Demo card *4242",
        )
    )
    if instrument is not None:
        return instrument
    instrument = PaymentInstrument(
        account=account,
        type="physical_card",
        masked_label="Demo card *4242",
        last_digits="4242",
    )
    db.add(instrument)
    db.flush()
    return instrument


def _get_or_create_category(db: Session, family: Family, name: str) -> Category:
    category = db.scalar(
        select(Category).where(
            Category.family_id == family.id,
            Category.name == name,
        )
    )
    if category is not None:
        return category
    category = Category(family=family, name=name, is_system=False)
    db.add(category)
    db.flush()
    return category


def _get_or_create_merchant(db: Session, family: Family, name: str, merchant_type: str) -> Merchant:
    normalized_name = name.casefold()
    merchant = db.scalar(
        select(Merchant).where(
            Merchant.family_id == family.id,
            Merchant.normalized_name == normalized_name,
        )
    )
    if merchant is not None:
        return merchant
    merchant = Merchant(
        family=family,
        name=name,
        normalized_name=normalized_name,
        merchant_type=merchant_type,
    )
    db.add(merchant)
    db.flush()
    return merchant


def _get_or_create_transaction(
    db: Session,
    family: Family,
    account: Account,
    item: dict,
) -> Transaction:
    bank_transaction_id = item["bank_transaction_id"]
    transaction = db.scalar(
        select(Transaction).where(
            Transaction.family_id == family.id,
            Transaction.bank_transaction_id == bank_transaction_id,
        )
    )
    if transaction is not None:
        return transaction
    transaction = Transaction(
        family=family,
        account=account,
        bank_transaction_id=bank_transaction_id,
        occurred_at=item["occurred_at"],
        amount=item["amount"],
        currency="UAH",
        direction=item["direction"],
        flow_type=item["flow_type"],
        scope=item["scope"],
        description_raw=item["description_raw"],
        merchant=item.get("merchant"),
        category=item.get("category"),
        needs_review=item.get("needs_review", False),
    )
    db.add(transaction)
    db.flush()
    return transaction


def _demo_transactions(categories: dict[str, Category], merchants: dict[str, Merchant]) -> list[dict]:
    return [
        {
            "bank_transaction_id": "demo-2026-05-01-income",
            "occurred_at": datetime(2026, 5, 1, 9, 0),
            "amount": Decimal("42000.00"),
            "direction": "income",
            "flow_type": "income",
            "scope": "family",
            "description_raw": "Salary",
        },
        {
            "bank_transaction_id": "demo-2026-05-01-silpo",
            "occurred_at": datetime(2026, 5, 1, 12, 0),
            "amount": Decimal("-1850.00"),
            "direction": "expense",
            "flow_type": "purchase",
            "scope": "family",
            "description_raw": "Silpo groceries",
            "category": categories["Еда"],
            "merchant": merchants["Silpo"],
        },
        {
            "bank_transaction_id": "demo-2026-05-02-atb",
            "occurred_at": datetime(2026, 5, 2, 18, 20),
            "amount": Decimal("-940.00"),
            "direction": "expense",
            "flow_type": "purchase",
            "scope": "family",
            "description_raw": "АТБ groceries",
            "category": categories["Еда"],
            "merchant": merchants["АТБ"],
        },
        {
            "bank_transaction_id": "demo-2026-05-03-pharmacy",
            "occurred_at": datetime(2026, 5, 3, 10, 30),
            "amount": Decimal("-720.00"),
            "direction": "expense",
            "flow_type": "purchase",
            "scope": "family",
            "description_raw": "Аптека",
            "category": categories["Здоровье"],
            "merchant": merchants["Аптека"],
        },
        {
            "bank_transaction_id": "demo-2026-05-04-school",
            "occurred_at": datetime(2026, 5, 4, 8, 40),
            "amount": Decimal("-4500.00"),
            "direction": "expense",
            "flow_type": "purchase",
            "scope": "family",
            "description_raw": "School payment",
            "category": categories["Дети"],
            "merchant": merchants["Школа"],
        },
        {
            "bank_transaction_id": "demo-2026-05-05-savings",
            "occurred_at": datetime(2026, 5, 5, 9, 15),
            "amount": Decimal("-650.00"),
            "direction": "expense",
            "flow_type": "transfer_to_savings",
            "scope": "family",
            "description_raw": "Скарбничка",
        },
        {
            "bank_transaction_id": "demo-2026-05-06-wife-transfer",
            "occurred_at": datetime(2026, 5, 6, 14, 0),
            "amount": Decimal("-2000.00"),
            "direction": "expense",
            "flow_type": "transfer_to_wife",
            "scope": "family",
            "description_raw": "Transfer to wife",
        },
        {
            "bank_transaction_id": "demo-2026-05-07-uncategorized",
            "occurred_at": datetime(2026, 5, 7, 19, 0),
            "amount": Decimal("-480.00"),
            "direction": "expense",
            "flow_type": "purchase",
            "scope": "family",
            "description_raw": "Market transfer",
            "needs_review": True,
        },
        {
            "bank_transaction_id": "demo-2026-05-08-fop-income",
            "occurred_at": datetime(2026, 5, 8, 11, 0),
            "amount": Decimal("12000.00"),
            "direction": "income",
            "flow_type": "income",
            "scope": "work_fop",
            "description_raw": "FOP client payment",
        },
        {
            "bank_transaction_id": "demo-2026-05-09-openai",
            "occurred_at": datetime(2026, 5, 9, 16, 0),
            "amount": Decimal("-820.00"),
            "direction": "expense",
            "flow_type": "purchase",
            "scope": "work_fop",
            "description_raw": "OpenAI subscription",
            "category": categories["Рабочее/FOP"],
            "merchant": merchants["OpenAI"],
        },
    ]


def main() -> None:
    with SessionLocal() as db:
        result = seed_demo_dashboard(db)
    print(f"Demo family_id: {result.family_id}")
    print(f"Demo account_id: {result.account_id}")
    print(f"Demo transactions: {result.transaction_count}")


if __name__ == "__main__":
    main()
