from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.category import Category, Subcategory
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.models.user import User
from app.services.import_review import normalize_review_text

CENT = Decimal("0.01")
INCOME_TYPES = {"income", "refund", "own_transfer", "debt", "other"}
INCOME_FLOW_BY_TYPE = {
    "income": "income",
    "refund": "refund",
    "own_transfer": "transfer_to_own_account",
    "debt": "income",
    "other": "income",
}
MANUAL_EXPENSE_FLOWS = {"purchase", "cash_expense", "subscription", "work_fop", "other"}
EDITABLE_EXPENSE_FLOWS = {
    "purchase",
    "cash_withdrawal",
    "cash_expense",
    "transfer_to_savings",
    "transfer_to_wife",
    "person_transfer",
    "requisites_payment",
    "subscription",
    "work_fop",
    "other",
}
SCOPES = {"family", "personal_main_user", "work_fop"}
AUDIT_SNAPSHOT_FIELDS = (
    "account_id",
    "occurred_at",
    "amount",
    "currency",
    "direction",
    "flow_type",
    "income_type",
    "scope",
    "merchant_name",
    "category_id",
    "subcategory_id",
    "comment",
    "needs_review",
    "is_cash",
)


class TransactionServiceError(ValueError):
    pass


class TransactionNotFoundError(TransactionServiceError):
    pass


class TransactionValidationError(TransactionServiceError):
    pass


class TransactionService:
    """Family-scoped transaction mutations shared by Web and Telegram."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_expense(
        self,
        *,
        user: User,
        account_id: UUID,
        amount: Decimal,
        occurred_at: datetime | None = None,
        merchant_name: str | None = None,
        category_id: UUID | None = None,
        subcategory_id: UUID | None = None,
        flow_type: str | None = None,
        scope: str = "family",
        comment: str | None = None,
        raw_text: str | None = None,
    ) -> Transaction:
        return self._create_manual(
            user=user,
            account_id=account_id,
            amount=amount,
            direction="expense",
            occurred_at=occurred_at,
            merchant_name=merchant_name,
            category_id=category_id,
            subcategory_id=subcategory_id,
            flow_type=flow_type,
            income_type=None,
            scope=scope,
            comment=comment,
            raw_text=raw_text,
        )

    def create_income(
        self,
        *,
        user: User,
        account_id: UUID,
        amount: Decimal,
        income_type: str = "income",
        occurred_at: datetime | None = None,
        merchant_name: str | None = None,
        category_id: UUID | None = None,
        subcategory_id: UUID | None = None,
        flow_type: str | None = None,
        scope: str = "family",
        comment: str | None = None,
        raw_text: str | None = None,
    ) -> Transaction:
        return self._create_manual(
            user=user,
            account_id=account_id,
            amount=amount,
            direction="income",
            occurred_at=occurred_at,
            merchant_name=merchant_name,
            category_id=category_id,
            subcategory_id=subcategory_id,
            flow_type=flow_type,
            income_type=income_type,
            scope=scope,
            comment=comment,
            raw_text=raw_text,
        )

    def get(self, *, user: User, transaction_id: UUID) -> Transaction:
        actor = self._get_actor(user)
        transaction = self._load_transaction(
            family_id=actor.family_id,
            transaction_id=transaction_id,
            include_deleted=False,
        )
        if transaction is None:
            raise TransactionNotFoundError("Transaction not found.")
        return transaction

    def update(
        self,
        *,
        user: User,
        transaction_id: UUID,
        changes: dict[str, Any],
    ) -> Transaction:
        allowed = {
            "account_id",
            "occurred_at",
            "amount",
            "direction",
            "merchant_name",
            "category_id",
            "subcategory_id",
            "flow_type",
            "income_type",
            "scope",
            "comment",
            "needs_review",
        }
        unexpected = set(changes) - allowed
        if unexpected:
            raise TransactionValidationError("Unsupported transaction fields.")

        actor = self._get_actor(user)
        transaction = self._load_transaction(
            family_id=actor.family_id,
            transaction_id=transaction_id,
            include_deleted=False,
            lock=True,
        )
        if transaction is None:
            raise TransactionNotFoundError("Transaction not found.")
        if not changes:
            return transaction

        targets: dict[str, Any] = {}
        audit_keys: dict[str, str] = {}

        direction, flow_type, income_type = self._updated_classification(transaction, changes)
        if direction != transaction.direction:
            targets["direction"] = direction
            audit_keys["direction"] = "direction"
        if flow_type != transaction.flow_type:
            targets["flow_type"] = flow_type
            audit_keys["flow_type"] = "flow_type"
        if income_type != transaction.income_type:
            targets["income_type"] = income_type
            audit_keys["income_type"] = "income_type"

        if direction != transaction.direction and direction in {"expense", "income"}:
            current_magnitude = abs(transaction.amount)
            targets["amount"] = current_magnitude if direction == "income" else -current_magnitude
            audit_keys["amount"] = "amount"

        if "amount" in changes:
            magnitude = _positive_amount(changes["amount"])
            if direction == "transfer":
                raise TransactionValidationError(
                    "A transfer amount cannot be edited as income or expense."
                )
            signed_amount = magnitude if direction == "income" else -magnitude
            targets["amount"] = signed_amount
            audit_keys["amount"] = "amount"

        if "occurred_at" in changes:
            occurred_at = _aware_utc(changes["occurred_at"])
            targets["occurred_at"] = occurred_at
            audit_keys["occurred_at"] = "occurred_at"

        if "account_id" in changes:
            if changes["account_id"] is None:
                raise TransactionValidationError("An account is required.")
            account = self._get_active_account(changes["account_id"], actor.family_id)
            targets["account_id"] = account.id
            audit_keys["account_id"] = "account_id"
            targets["currency"] = account.currency
            audit_keys["currency"] = "currency"

        if "scope" in changes:
            scope = changes["scope"]
            if scope not in SCOPES:
                raise TransactionValidationError("Invalid transaction scope.")
            targets["scope"] = scope
            audit_keys["scope"] = "scope"

        if "comment" in changes:
            targets["comment"] = _clean_optional_text(changes["comment"])
            audit_keys["comment"] = "comment"

        if "needs_review" in changes:
            if not isinstance(changes["needs_review"], bool):
                raise TransactionValidationError("Invalid review status.")
            targets["needs_review"] = changes["needs_review"]
            audit_keys["needs_review"] = "needs_review"

        category = transaction.category
        if "category_id" in changes:
            category = self._get_category(changes["category_id"], actor.family_id)
            targets["category_id"] = category.id if category else None
            audit_keys["category_id"] = "category_id"
            if category is None or category.id != transaction.category_id:
                targets["subcategory_id"] = None
                audit_keys["subcategory_id"] = "subcategory_id"

        if "subcategory_id" in changes:
            selected_category_id = targets.get("category_id", transaction.category_id)
            subcategory = self._get_subcategory(
                changes["subcategory_id"], category_id=selected_category_id
            )
            targets["subcategory_id"] = subcategory.id if subcategory else None
            audit_keys["subcategory_id"] = "subcategory_id"

        if "merchant_name" in changes:
            merchant_name = _clean_merchant_name(changes["merchant_name"])
            current_display_name = _display_description(transaction)
            if merchant_name != current_display_name:
                merchant = self._get_or_create_merchant(actor.family_id, merchant_name)
                targets["merchant_id"] = merchant.id if merchant else None
                targets["description_override"] = merchant_name
                audit_keys["merchant_id"] = "merchant_name"
                audit_keys["description_override"] = "merchant_name"

        changed_keys: set[str] = set()
        before_values: dict[str, str | bool | None] = {}
        for attribute, target in targets.items():
            current = getattr(transaction, attribute)
            if _values_equal(attribute, current, target, transaction):
                continue
            audit_key = audit_keys[attribute]
            if audit_key not in changed_keys:
                before_values[audit_key] = _serialize_audit_value(
                    _audit_attribute_value(transaction, audit_key), transaction
                )
                changed_keys.add(audit_key)
            setattr(transaction, attribute, target)

        if not changed_keys:
            return transaction

        after_values = {
            key: _serialize_audit_value(_audit_attribute_value(transaction, key), transaction)
            for key in changed_keys
        }
        self._commit_with_audit(
            transaction,
            actor=actor,
            action="update",
            before_payload=before_values,
            after_payload=after_values,
        )
        return self._refresh(transaction)

    def soft_delete(self, *, user: User, transaction_id: UUID) -> Transaction:
        actor = self._get_actor(user)
        transaction = self._load_transaction(
            family_id=actor.family_id,
            transaction_id=transaction_id,
            include_deleted=True,
            lock=True,
        )
        if transaction is None:
            raise TransactionNotFoundError("Transaction not found.")
        if transaction.deleted_at is not None:
            return transaction

        now = datetime.now(UTC)
        before_payload = {"deleted_at": None, "deleted_by_user_id": None}
        transaction.deleted_at = now
        transaction.deleted_by_user_id = actor.id
        self._commit_with_audit(
            transaction,
            actor=actor,
            action="delete",
            before_payload=before_payload,
            after_payload={
                "deleted_at": now.isoformat(),
                "deleted_by_user_id": str(actor.id),
            },
        )
        return self._refresh(transaction)

    def _create_manual(
        self,
        *,
        user: User,
        account_id: UUID,
        amount: Decimal,
        direction: str,
        occurred_at: datetime | None,
        merchant_name: str | None,
        category_id: UUID | None,
        subcategory_id: UUID | None,
        flow_type: str | None,
        income_type: str | None,
        scope: str,
        comment: str | None,
        raw_text: str | None,
    ) -> Transaction:
        actor = self._get_actor(user)
        magnitude = _positive_amount(amount)
        if scope not in SCOPES:
            raise TransactionValidationError("Invalid transaction scope.")
        normalized_flow, normalized_income_type = _manual_classification(
            direction, flow_type, income_type
        )
        account = self._get_active_account(account_id, actor.family_id)
        category = self._get_category(category_id, actor.family_id)
        subcategory = self._get_subcategory(
            subcategory_id,
            category_id=category.id if category is not None else None,
        )
        clean_name = _clean_merchant_name(merchant_name)
        merchant = self._get_or_create_merchant(actor.family_id, clean_name)
        timestamp = _aware_utc(occurred_at) if occurred_at is not None else datetime.now(UTC)
        transaction = Transaction(
            family_id=actor.family_id,
            account_id=account.id,
            owner_user_id=actor.id,
            occurred_at=timestamp,
            amount=magnitude if direction == "income" else -magnitude,
            currency=account.currency,
            direction=direction,
            flow_type=normalized_flow,
            income_type=normalized_income_type,
            scope=scope,
            description_raw=raw_text.strip() if raw_text and raw_text.strip() else clean_name,
            description_normalized=normalize_review_text(clean_name) or None,
            description_override=clean_name,
            merchant_id=merchant.id if merchant else None,
            category_id=category.id if category else None,
            subcategory_id=subcategory.id if subcategory else None,
            comment=_clean_optional_text(comment),
            is_cash=account.type == "cash" or normalized_flow == "cash_expense",
            needs_review=category is None,
        )
        self.db.add(transaction)
        self.db.flush()
        self._commit_with_audit(
            transaction,
            actor=actor,
            action="create",
            before_payload=None,
            after_payload=_snapshot(transaction),
        )
        return self._refresh(transaction)

    def _get_actor(self, user: User) -> User:
        actor = self.db.scalar(select(User).where(User.id == user.id, User.is_active.is_(True)))
        if actor is None:
            raise TransactionValidationError("User is not available.")
        return actor

    def _get_active_account(self, account_id: UUID, family_id: UUID) -> Account:
        account = self.db.scalar(
            select(Account).where(
                Account.id == account_id,
                Account.family_id == family_id,
                Account.is_active.is_(True),
            )
        )
        if account is None:
            raise TransactionValidationError("Account not found or inactive.")
        if account.owner_user_id is not None:
            owner = self.db.scalar(
                select(User.id).where(
                    User.id == account.owner_user_id,
                    User.family_id == family_id,
                )
            )
            if owner is None:
                raise TransactionValidationError("Account not found or inactive.")
        return account

    def _get_category(self, category_id: UUID | None, family_id: UUID) -> Category | None:
        if category_id is None:
            return None
        category = self.db.scalar(
            select(Category).where(
                Category.id == category_id,
                or_(Category.family_id == family_id, Category.family_id.is_(None)),
            )
        )
        if category is None:
            raise TransactionValidationError("Category not found.")
        return category

    def _get_subcategory(
        self,
        subcategory_id: UUID | None,
        *,
        category_id: UUID | None,
    ) -> Subcategory | None:
        if subcategory_id is None:
            return None
        if category_id is None:
            raise TransactionValidationError("A subcategory requires a category.")
        subcategory = self.db.scalar(
            select(Subcategory).where(
                Subcategory.id == subcategory_id,
                Subcategory.category_id == category_id,
            )
        )
        if subcategory is None:
            raise TransactionValidationError(
                "Subcategory does not belong to the selected category."
            )
        return subcategory

    def _get_or_create_merchant(self, family_id: UUID, name: str | None) -> Merchant | None:
        normalized_name = normalize_review_text(name)
        if not name or not normalized_name:
            return None
        merchant = self.db.scalar(
            select(Merchant).where(
                Merchant.family_id == family_id,
                Merchant.normalized_name == normalized_name,
            )
        )
        if merchant is not None:
            return merchant
        merchant = Merchant(
            family_id=family_id,
            name=name,
            normalized_name=normalized_name,
            merchant_type="manual",
        )
        self.db.add(merchant)
        self.db.flush()
        return merchant

    def _load_transaction(
        self,
        *,
        family_id: UUID,
        transaction_id: UUID,
        include_deleted: bool,
        lock: bool = False,
    ) -> Transaction | None:
        query = (
            select(Transaction)
            .options(
                joinedload(Transaction.account),
                joinedload(Transaction.merchant),
                joinedload(Transaction.category),
                joinedload(Transaction.subcategory),
            )
            .where(Transaction.id == transaction_id, Transaction.family_id == family_id)
        )
        if not include_deleted:
            query = query.where(Transaction.deleted_at.is_(None))
        if lock:
            query = query.with_for_update(of=Transaction)
        return self.db.scalar(query)

    def _commit_with_audit(
        self,
        transaction: Transaction,
        *,
        actor: User,
        action: str,
        before_payload: dict[str, Any] | None,
        after_payload: dict[str, Any] | None,
    ) -> None:
        self.db.add(
            AuditLog(
                family_id=transaction.family_id,
                user_id=actor.id,
                entity_type="transaction",
                entity_id=transaction.id,
                action=action,
                before_payload=before_payload,
                after_payload=after_payload,
            )
        )
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _refresh(self, transaction: Transaction) -> Transaction:
        self.db.refresh(transaction)
        self.db.expire(
            transaction,
            ["account", "payment_instrument", "merchant", "category", "subcategory"],
        )
        return transaction

    def _updated_classification(
        self,
        transaction: Transaction,
        changes: dict[str, Any],
    ) -> tuple[str, str, str | None]:
        direction = changes.get("direction", transaction.direction)
        flow_type = changes.get("flow_type", transaction.flow_type)
        income_type = changes.get("income_type", transaction.income_type)
        direction_changed = direction != transaction.direction

        if direction_changed and direction == "expense":
            income_type = changes.get("income_type") if "income_type" in changes else None
            if "flow_type" not in changes:
                flow_type = "purchase"
        elif direction_changed and direction == "income":
            income_type = income_type if income_type in INCOME_TYPES else "income"
            if "flow_type" not in changes:
                flow_type = INCOME_FLOW_BY_TYPE[income_type]
        elif direction == "income" and "income_type" in changes and "flow_type" not in changes:
            selected_income_type = income_type or "income"
            income_type = selected_income_type
            flow_type = INCOME_FLOW_BY_TYPE.get(selected_income_type, flow_type)

        if direction not in {"expense", "income", "transfer"}:
            raise TransactionValidationError("Invalid transaction direction.")
        if direction == "transfer" and any(
            key in changes for key in ("direction", "flow_type", "income_type")
        ):
            raise TransactionValidationError("Manual transfer classification is not supported.")
        if direction in {"expense", "income"} and any(
            key in changes for key in ("direction", "flow_type", "income_type")
        ):
            self._validate_edit_classification(direction, flow_type, income_type)
        return direction, flow_type, income_type

    @staticmethod
    def _validate_edit_classification(
        direction: str,
        flow_type: str,
        income_type: str | None,
    ) -> None:
        if direction == "expense":
            if flow_type not in EDITABLE_EXPENSE_FLOWS or income_type is not None:
                raise TransactionValidationError("Expense flow and income type do not match.")
            return
        selected_income_type = income_type or "income"
        if selected_income_type not in INCOME_TYPES:
            raise TransactionValidationError("Invalid income type.")
        if INCOME_FLOW_BY_TYPE[selected_income_type] != flow_type:
            raise TransactionValidationError("Income flow and income type do not match.")


def _manual_classification(
    direction: str,
    flow_type: str | None,
    income_type: str | None,
) -> tuple[str, str | None]:
    if direction == "expense":
        selected_flow = flow_type or "purchase"
        if selected_flow not in MANUAL_EXPENSE_FLOWS or income_type is not None:
            raise TransactionValidationError("Expense flow and income type do not match.")
        return selected_flow, None
    if direction != "income":
        raise TransactionValidationError("Manual transactions must be expenses or incomes.")
    selected_income_type = income_type or "income"
    if selected_income_type not in INCOME_TYPES:
        raise TransactionValidationError("Invalid income type.")
    expected_flow = INCOME_FLOW_BY_TYPE[selected_income_type]
    if flow_type is not None and flow_type != expected_flow:
        raise TransactionValidationError("Income flow and income type do not match.")
    return expected_flow, selected_income_type


def _positive_amount(value: Any) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise TransactionValidationError("Amount must be a positive decimal value.")
    try:
        quantized = value.quantize(CENT)
    except Exception as exc:
        raise TransactionValidationError("Amount supports at most two decimal places.") from exc
    if quantized != value or quantized >= Decimal("1000000000000"):
        raise TransactionValidationError("Amount supports at most two decimal places.")
    return quantized


def _aware_utc(value: Any) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise TransactionValidationError("Datetime must include a timezone offset.")
    return value.astimezone(UTC)


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TransactionValidationError("Text value is invalid.")
    return value.strip() or None


def _clean_merchant_name(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TransactionValidationError("Merchant name is invalid.")
    normalized_spacing = " ".join(value.split())
    return normalized_spacing[:255] or None


def _display_description(transaction: Transaction) -> str | None:
    return (
        transaction.description_override
        or (transaction.merchant.name if transaction.merchant else None)
        or transaction.description_normalized
        or transaction.description_raw
    )


def _snapshot(transaction: Transaction) -> dict[str, str | bool | None]:
    return {
        key: _serialize_audit_value(_audit_attribute_value(transaction, key), transaction)
        for key in AUDIT_SNAPSHOT_FIELDS
    }


def _audit_attribute_value(transaction: Transaction, key: str) -> Any:
    if key == "merchant_name":
        return _display_description(transaction)
    return getattr(transaction, key)


def _serialize_audit_value(value: Any, transaction: Transaction | None = None) -> str | bool | None:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, datetime):
        if value.tzinfo is None and transaction is not None and transaction.import_batch_id is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    if isinstance(value, str):
        return value
    return str(value)


def _values_equal(attribute: str, current: Any, target: Any, transaction: Transaction) -> bool:
    if (
        attribute != "occurred_at"
        or not isinstance(current, datetime)
        or not isinstance(target, datetime)
    ):
        return current == target
    if current.tzinfo is None and target.tzinfo is not None and transaction.import_batch_id is None:
        return current.replace(tzinfo=UTC) == target.astimezone(UTC)
    if current.tzinfo is not None and target.tzinfo is not None:
        return current.astimezone(UTC) == target.astimezone(UTC)
    return current == target
