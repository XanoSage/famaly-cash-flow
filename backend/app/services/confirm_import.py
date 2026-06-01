from __future__ import annotations

from decimal import Decimal
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account, PaymentInstrument
from app.models.import_batch import ImportBatch, ImportPreviewRow
from app.models.merchant import Merchant
from app.models.transaction import Transaction


class ConfirmImportError(ValueError):
    pass


class ConfirmImportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def confirm(
        self,
        *,
        family_id: UUID,
        import_batch_id: UUID,
        account_id: UUID,
        owner_user_id: UUID | None = None,
    ) -> list[Transaction]:
        import_batch = self._get_draft_import_batch(family_id, import_batch_id)
        account = self._get_account(family_id, account_id)
        preview_rows = self._get_preview_rows(import_batch.id)

        error_rows = [row for row in preview_rows if row.status == "error"]
        if error_rows:
            raise ConfirmImportError("Import preview contains error rows.")

        transactions = [
            self._create_transaction(import_batch, account, row, owner_user_id)
            for row in preview_rows
            if row.status not in {"excluded", "duplicate_candidate"}
        ]

        import_batch.status = "confirmed"
        import_batch.imported_count = len(transactions)
        import_batch.excluded_count = sum(row.status == "excluded" for row in preview_rows)
        import_batch.duplicate_count = sum(row.status == "duplicate_candidate" for row in preview_rows)
        import_batch.error_count = len(error_rows)

        self.db.add_all(transactions)
        self.db.commit()
        for transaction in transactions:
            self.db.refresh(transaction)
        return transactions

    def _get_draft_import_batch(self, family_id: UUID, import_batch_id: UUID) -> ImportBatch:
        import_batch = self.db.scalar(
            select(ImportBatch).where(
                ImportBatch.id == import_batch_id,
                ImportBatch.family_id == family_id,
            )
        )
        if import_batch is None:
            raise ConfirmImportError("Import preview not found.")
        if import_batch.status != "draft":
            raise ConfirmImportError("Only draft imports can be confirmed.")
        return import_batch

    def _get_account(self, family_id: UUID, account_id: UUID) -> Account:
        account = self.db.scalar(
            select(Account).where(
                Account.id == account_id,
                Account.family_id == family_id,
            )
        )
        if account is None:
            raise ConfirmImportError("Account not found.")
        return account

    def _get_preview_rows(self, import_batch_id: UUID) -> list[ImportPreviewRow]:
        return self.db.scalars(
            select(ImportPreviewRow)
            .where(ImportPreviewRow.import_batch_id == import_batch_id)
            .order_by(ImportPreviewRow.row_number)
        ).all()

    def _create_transaction(
        self,
        import_batch: ImportBatch,
        account: Account,
        row: ImportPreviewRow,
        owner_user_id: UUID | None,
    ) -> Transaction:
        if row.occurred_at is None or row.amount is None:
            raise ConfirmImportError(f"Preview row {row.row_number} is missing required transaction fields.")

        flow_type = row.proposed_flow_type or "other"
        direction = _direction_from_amount(row.amount)
        merchant = self._get_or_create_merchant(import_batch.family_id, row.merchant_name)
        payment_instrument = self._get_or_create_payment_instrument(account.id, row.payment_instrument_label)

        return Transaction(
            family_id=import_batch.family_id,
            account_id=account.id,
            payment_instrument_id=payment_instrument.id if payment_instrument else None,
            owner_user_id=owner_user_id or account.owner_user_id,
            import_batch_id=import_batch.id,
            occurred_at=row.occurred_at,
            amount=row.amount,
            currency=row.currency or account.currency,
            transaction_amount=row.transaction_amount,
            transaction_currency=row.transaction_currency,
            balance_after=row.balance_after,
            direction=direction,
            flow_type=flow_type,
            income_type="income" if direction == "income" else None,
            scope=row.proposed_scope or "family",
            description_raw=row.description_raw,
            description_normalized=_normalize_text(row.description_raw),
            bank_category_raw=row.bank_category_raw,
            merchant_id=merchant.id if merchant else None,
            category_id=row.proposed_category_id,
            subcategory_id=row.proposed_subcategory_id,
            is_cash=flow_type in {"cash_withdrawal", "cash_expense"},
            is_duplicate_candidate=row.status == "duplicate_candidate",
            needs_review=row.status == "needs_review",
        )

    def _get_or_create_merchant(self, family_id: UUID, merchant_name: str | None) -> Merchant | None:
        normalized_name = _normalize_text(merchant_name)
        if not merchant_name or not normalized_name:
            return None

        merchant = self.db.scalar(
            select(Merchant).where(
                Merchant.family_id == family_id,
                Merchant.normalized_name == normalized_name,
            )
        )
        if merchant:
            return merchant

        merchant = Merchant(
            family_id=family_id,
            name=merchant_name,
            normalized_name=normalized_name,
            merchant_type="unknown",
        )
        self.db.add(merchant)
        self.db.flush()
        return merchant

    def _get_or_create_payment_instrument(
        self,
        account_id: UUID,
        label: str | None,
    ) -> PaymentInstrument | None:
        if not label:
            return None

        payment_instrument = self.db.scalar(
            select(PaymentInstrument).where(
                PaymentInstrument.account_id == account_id,
                PaymentInstrument.masked_label == label,
            )
        )
        if payment_instrument:
            return payment_instrument

        payment_instrument = PaymentInstrument(
            account_id=account_id,
            type="card",
            masked_label=label,
            last_digits=_extract_last_digits(label),
        )
        self.db.add(payment_instrument)
        self.db.flush()
        return payment_instrument


def _direction_from_amount(amount: Decimal) -> str:
    if amount < 0:
        return "expense"
    if amount > 0:
        return "income"
    return "transfer"


def _normalize_text(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip().casefold()


def _extract_last_digits(label: str) -> str | None:
    digits = re.findall(r"\d", label)
    if len(digits) < 4:
        return None
    return "".join(digits[-4:])
