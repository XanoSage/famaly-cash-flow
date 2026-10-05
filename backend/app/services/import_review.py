from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.categorization_rule import CategorizationRule
from app.models.category import Category, Subcategory
from app.models.import_batch import ImportBatch, ImportPreviewRow
from app.models.transaction import Transaction

VALID_FLOW_TYPES = {
    "purchase",
    "cash_withdrawal",
    "cash_expense",
    "transfer_to_own_account",
    "transfer_to_savings",
    "transfer_to_wife",
    "person_transfer",
    "requisites_payment",
    "refund",
    "income",
    "subscription",
    "work_fop",
    "other",
}
VALID_SCOPES = {"family", "personal_main_user", "work_fop"}
REVIEW_REASON_CODES = {
    "new_merchant",
    "large_amount",
    "large_supermarket",
    "person_transfer",
    "wife_transfer",
    "requisites_payment",
    "low_confidence",
    "work_fop_candidate",
}
GENERATED_REASON_CODES = {"duplicate", "uncategorized", "rule_conflict", "parse_error"}
RULE_OUTPUT_FIELDS = {
    "category_id": "proposed_category_id",
    "subcategory_id": "proposed_subcategory_id",
    "flow_type": "proposed_flow_type",
    "scope": "proposed_scope",
}


class ImportReviewError(ValueError):
    """Base error for import review operations."""


class ImportDraftNotFoundError(ImportReviewError):
    pass


class ImportReviewValidationError(ImportReviewError):
    pass


@dataclass(frozen=True)
class ImportReviewResult:
    batch: ImportBatch
    rows: list[ImportPreviewRow]
    requested_count: int
    matched_count: int
    changed_count: int


def normalize_review_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip().casefold()


class ImportReviewService:
    """Owns family-scoped preview categorization, duplicate matching, and review edits."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def prepare_preview(self, *, family_id: UUID, import_batch_id: UUID) -> ImportBatch:
        batch = self._get_draft(family_id, import_batch_id, lock=False)
        rows = self._get_rows(batch.id)
        rules = self._get_rules(family_id)
        for row in rows:
            self._apply_rules(row, rules, family_id)
        self._match_duplicates(family_id, rows)
        self.recompute_batch_summary(batch, rows)
        self.db.flush()
        return batch

    def get_batch(
        self, *, family_id: UUID, import_batch_id: UUID, draft_only: bool = False
    ) -> ImportBatch:
        query = select(ImportBatch).where(
            ImportBatch.id == import_batch_id,
            ImportBatch.family_id == family_id,
        )
        batch = self.db.scalar(query)
        if batch is None:
            raise ImportDraftNotFoundError("Import preview not found.")
        if draft_only and batch.status != "draft":
            raise ImportReviewValidationError("Only draft imports can be edited.")
        return batch

    def patch_row(
        self,
        *,
        family_id: UUID,
        import_batch_id: UUID,
        row_id: UUID,
        changes: dict[str, object],
        save_rule: bool = False,
        apply_to_merchant: bool = False,
    ) -> ImportReviewResult:
        return self._update_rows(
            family_id=family_id,
            import_batch_id=import_batch_id,
            row_ids=[row_id],
            changes=changes,
            save_rule=save_rule,
            apply_to_merchant=apply_to_merchant,
        )

    def bulk_action(
        self,
        *,
        family_id: UUID,
        import_batch_id: UUID,
        row_ids: list[UUID],
        action: str,
        values: dict[str, object],
        save_rule: bool = False,
        apply_to_merchant: bool = False,
    ) -> ImportReviewResult:
        if action not in {
            "assign_category",
            "set_scope",
            "set_flow_type",
            "exclude",
            "include_duplicate",
            "mark_uncategorized",
            "apply_correction",
        }:
            raise ImportReviewValidationError("Unsupported import review action.")

        changes = dict(values)
        if action == "exclude":
            changes["excluded"] = True
        elif action == "include_duplicate":
            changes["include_duplicate"] = True
        elif action == "mark_uncategorized":
            changes["accept_uncategorized"] = True
        elif action == "assign_category" and not {
            "proposed_category_id",
            "proposed_subcategory_id",
        }.intersection(changes):
            raise ImportReviewValidationError("A category or subcategory is required.")
        elif action == "set_scope" and "proposed_scope" not in changes:
            raise ImportReviewValidationError("A scope is required.")
        elif action == "set_flow_type" and "proposed_flow_type" not in changes:
            raise ImportReviewValidationError("A flow type is required.")
        elif action == "apply_correction" and not changes:
            raise ImportReviewValidationError("At least one correction field is required.")

        return self._update_rows(
            family_id=family_id,
            import_batch_id=import_batch_id,
            row_ids=row_ids,
            changes=changes,
            save_rule=save_rule,
            apply_to_merchant=apply_to_merchant,
        )

    def recompute_batch_summary(
        self,
        batch: ImportBatch,
        rows: list[ImportPreviewRow] | None = None,
    ) -> None:
        rows = rows if rows is not None else self._get_rows(batch.id)
        statuses = Counter(row.status for row in rows)
        batch.total_rows = len(rows)
        batch.auto_ready_count = statuses["auto_ready"]
        batch.needs_review_count = statuses["needs_review"]
        batch.imported_count = sum(
            row.status in {"auto_ready", "needs_review"}
            or (row.status == "duplicate_candidate" and row.duplicate_included)
            for row in rows
        )
        batch.excluded_count = statuses["excluded"]
        batch.duplicate_count = sum("duplicate" in row.reason_codes for row in rows)
        batch.error_count = statuses["error"]
        batch.uncategorized_count = sum(row.proposed_category_id is None for row in rows)
        batch.work_fop_count = sum(row.proposed_scope == "work_fop" for row in rows)
        batch.savings_count = sum(row.proposed_flow_type == "transfer_to_savings" for row in rows)

    def recompute_row(self, row: ImportPreviewRow) -> None:
        payload = dict(row.normalized_payload or {})
        base_reasons = payload.get("base_reason_codes")
        if not isinstance(base_reasons, list):
            base_reasons = [code for code in row.reason_codes if code not in GENERATED_REASON_CODES]
            payload["base_reason_codes"] = base_reasons
        reasons = [
            code
            for code in base_reasons
            if isinstance(code, str) and code not in GENERATED_REASON_CODES
        ]

        parse_error = (
            "parse_error" in base_reasons
            or row.error_message is not None
            or row.occurred_at is None
            or row.amount is None
        )
        if parse_error:
            reasons.append("parse_error")

        conflict_fields = payload.get("rule_conflict_fields", [])
        if isinstance(conflict_fields, list) and conflict_fields:
            reasons.append("rule_conflict")

        has_duplicate = self._has_duplicate(row)
        if has_duplicate:
            reasons.append("duplicate")

        uncategorized = row.proposed_category_id is None and not row.reviewed_uncategorized
        if uncategorized:
            reasons.append("uncategorized")

        row.reason_codes = list(dict.fromkeys(reasons))
        user_excluded = payload.get("user_excluded") is True
        if user_excluded:
            row.status = "excluded"
        elif parse_error:
            row.status = "error"
        elif has_duplicate and not row.duplicate_included:
            row.status = "duplicate_candidate"
        elif conflict_fields or uncategorized:
            row.status = "needs_review"
        elif row.reviewed_at is None and any(code in REVIEW_REASON_CODES for code in base_reasons):
            row.status = "needs_review"
        else:
            row.status = "auto_ready"
        row.normalized_payload = payload

    def validate_category_selection(
        self,
        *,
        family_id: UUID,
        category_id: UUID | None,
        subcategory_id: UUID | None,
    ) -> None:
        if category_id is None:
            if subcategory_id is not None:
                raise ImportReviewValidationError("A subcategory requires a selected category.")
            return
        if self._get_allowed_category(family_id, category_id) is None:
            raise ImportReviewValidationError("Category not found in this family.")
        if (
            subcategory_id is not None
            and self._get_allowed_subcategory(family_id, category_id, subcategory_id) is None
        ):
            raise ImportReviewValidationError(
                "Subcategory must belong to the selected family category."
            )

    def _update_rows(
        self,
        *,
        family_id: UUID,
        import_batch_id: UUID,
        row_ids: list[UUID],
        changes: dict[str, object],
        save_rule: bool,
        apply_to_merchant: bool,
    ) -> ImportReviewResult:
        if not row_ids:
            raise ImportReviewValidationError("At least one preview row ID is required.")
        if len(set(row_ids)) != len(row_ids):
            raise ImportReviewValidationError("Preview row IDs must be unique.")
        if not changes:
            raise ImportReviewValidationError("At least one review decision is required.")

        batch = self._get_draft(family_id, import_batch_id, lock=True)
        batch_rows = self._get_rows(batch.id)
        rows_by_id = {row.id: row for row in batch_rows}
        selected = [rows_by_id[row_id] for row_id in row_ids if row_id in rows_by_id]
        if len(selected) != len(row_ids):
            raise ImportReviewValidationError(
                "One or more rows do not belong to this draft import."
            )

        targets = selected
        if apply_to_merchant:
            merchant_names = {normalize_review_text(row.merchant_name) for row in selected}
            if "" in merchant_names:
                raise ImportReviewValidationError(
                    "Merchant-wide changes require every selected row to have a merchant."
                )
            targets = [
                row
                for row in batch_rows
                if normalize_review_text(row.merchant_name) in merchant_names
            ]

        normalized_changes = dict(changes)
        if "merchant_name" in normalized_changes:
            merchant_name = normalized_changes["merchant_name"]
            if merchant_name is not None and not isinstance(merchant_name, str):
                raise ImportReviewValidationError("Merchant name must be text or null.")
            normalized_changes["merchant_name"] = (
                merchant_name.strip()[:255] if isinstance(merchant_name, str) else None
            )
        self._validate_enum_changes(normalized_changes)
        self._validate_category_changes(family_id, targets, normalized_changes)

        before = {row.id: self._review_state(row) for row in targets}
        now = datetime.now(UTC)
        try:
            for row in targets:
                self._apply_changes(row, normalized_changes, now)

            self._match_duplicates(family_id, batch_rows)
            for row in batch_rows:
                self.recompute_row(row)

            if save_rule:
                self._save_rules_for_rows(family_id, targets)

            self.recompute_batch_summary(batch, batch_rows)
            changed_count = sum(before[row.id] != self._review_state(row) for row in targets)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        for row in targets:
            self.db.refresh(row)
        self.db.refresh(batch)
        return ImportReviewResult(
            batch=batch,
            rows=targets,
            requested_count=len(row_ids),
            matched_count=len(targets),
            changed_count=changed_count,
        )

    def _apply_changes(
        self,
        row: ImportPreviewRow,
        changes: dict[str, object],
        now: datetime,
    ) -> None:
        payload = dict(row.normalized_payload or {})
        conflict_fields = set(payload.get("rule_conflict_fields", []))
        edited_rule_fields: set[str] = set()

        if "proposed_category_id" in changes:
            category_id = changes["proposed_category_id"]
            row.proposed_category_id = category_id if isinstance(category_id, UUID) else None
            edited_rule_fields.add("category_id")
            if row.proposed_subcategory_id is not None:
                subcategory = self.db.get(Subcategory, row.proposed_subcategory_id)
                if (
                    category_id is None
                    or subcategory is None
                    or subcategory.category_id != category_id
                ):
                    row.proposed_subcategory_id = None
                    edited_rule_fields.add("subcategory_id")
            if category_id is not None:
                row.reviewed_uncategorized = False

        if "proposed_subcategory_id" in changes:
            subcategory_id = changes["proposed_subcategory_id"]
            row.proposed_subcategory_id = (
                subcategory_id if isinstance(subcategory_id, UUID) else None
            )
            edited_rule_fields.add("subcategory_id")

        if "proposed_flow_type" in changes:
            value = changes["proposed_flow_type"]
            row.proposed_flow_type = value if isinstance(value, str) else None
            edited_rule_fields.add("flow_type")

        if "proposed_scope" in changes:
            value = changes["proposed_scope"]
            row.proposed_scope = value if isinstance(value, str) else None
            edited_rule_fields.add("scope")

        if "merchant_name" in changes:
            value = changes["merchant_name"]
            row.merchant_name = value if isinstance(value, str) else None

        if "excluded" in changes:
            payload["user_excluded"] = changes["excluded"] is True

        if "include_duplicate" in changes:
            include = changes["include_duplicate"] is True
            if include and not self._has_duplicate(row):
                raise ImportReviewValidationError("This preview row is not a duplicate candidate.")
            row.duplicate_included = include

        if changes.get("accept_uncategorized") is True:
            row.proposed_category_id = None
            row.proposed_subcategory_id = None
            row.reviewed_uncategorized = True
            edited_rule_fields.update({"category_id", "subcategory_id"})
        elif "accept_uncategorized" in changes and changes["accept_uncategorized"] is False:
            row.reviewed_uncategorized = False

        if edited_rule_fields or "merchant_name" in changes or "accept_uncategorized" in changes:
            row.reviewed_at = now
        payload["rule_conflict_fields"] = sorted(conflict_fields - edited_rule_fields)
        row.normalized_payload = payload

    def _validate_enum_changes(self, changes: dict[str, object]) -> None:
        flow_type = changes.get("proposed_flow_type")
        if flow_type is not None and flow_type not in VALID_FLOW_TYPES:
            raise ImportReviewValidationError("Invalid flow type.")
        scope = changes.get("proposed_scope")
        if scope is not None and scope not in VALID_SCOPES:
            raise ImportReviewValidationError("Invalid scope.")
        if "excluded" in changes and not isinstance(changes["excluded"], bool):
            raise ImportReviewValidationError("Excluded must be a boolean.")
        if "include_duplicate" in changes and not isinstance(changes["include_duplicate"], bool):
            raise ImportReviewValidationError("Include duplicate must be a boolean.")
        if "accept_uncategorized" in changes and not isinstance(
            changes["accept_uncategorized"], bool
        ):
            raise ImportReviewValidationError("Accept uncategorized must be a boolean.")
        if changes.get("accept_uncategorized") is True and (
            changes.get("proposed_category_id") is not None
            or changes.get("proposed_subcategory_id") is not None
        ):
            raise ImportReviewValidationError(
                "An uncategorized decision cannot include a category or subcategory."
            )

    def _validate_category_changes(
        self,
        family_id: UUID,
        rows: list[ImportPreviewRow],
        changes: dict[str, object],
    ) -> None:
        if not rows:
            return
        category_changed = "proposed_category_id" in changes
        subcategory_changed = "proposed_subcategory_id" in changes
        if not category_changed and not subcategory_changed:
            if changes.get("accept_uncategorized") is True:
                return
            return

        category_id = changes.get("proposed_category_id") if category_changed else None
        if category_changed and category_id is not None:
            if (
                not isinstance(category_id, UUID)
                or self._get_allowed_category(family_id, category_id) is None
            ):
                raise ImportReviewValidationError("Category not found in this family.")

        subcategory_id = changes.get("proposed_subcategory_id") if subcategory_changed else None
        for row in rows:
            selected_category_id = category_id if category_changed else row.proposed_category_id
            if not category_changed and selected_category_id is not None:
                if self._get_allowed_category(family_id, selected_category_id) is None:
                    raise ImportReviewValidationError("Category not found in this family.")
            if subcategory_changed and subcategory_id is None:
                continue
            if subcategory_changed and subcategory_id is not None:
                if not isinstance(subcategory_id, UUID) or selected_category_id is None:
                    raise ImportReviewValidationError("A subcategory requires a selected category.")
                if (
                    self._get_allowed_subcategory(family_id, selected_category_id, subcategory_id)
                    is None
                ):
                    raise ImportReviewValidationError(
                        "Subcategory must belong to the selected family category."
                    )
            elif category_changed and row.proposed_subcategory_id is not None:
                current_subcategory = self.db.get(Subcategory, row.proposed_subcategory_id)
                if (
                    current_subcategory is not None
                    and current_subcategory.category_id != selected_category_id
                ):
                    # Changing a category clears an incompatible existing subcategory.
                    continue

    def _get_allowed_category(self, family_id: UUID, category_id: UUID) -> Category | None:
        return self.db.scalar(
            select(Category).where(
                Category.id == category_id,
                or_(
                    Category.family_id == family_id,
                    (Category.family_id.is_(None) & Category.is_system.is_(True)),
                ),
            )
        )

    def _get_allowed_subcategory(
        self, family_id: UUID, category_id: UUID, subcategory_id: UUID
    ) -> Subcategory | None:
        return self.db.scalar(
            select(Subcategory)
            .join(Category, Category.id == Subcategory.category_id)
            .where(
                Subcategory.id == subcategory_id,
                Subcategory.category_id == category_id,
                or_(
                    Category.family_id == family_id,
                    (Category.family_id.is_(None) & Category.is_system.is_(True)),
                ),
            )
        )

    def _get_draft(self, family_id: UUID, import_batch_id: UUID, *, lock: bool) -> ImportBatch:
        query = select(ImportBatch).where(
            ImportBatch.id == import_batch_id,
            ImportBatch.family_id == family_id,
        )
        if lock:
            query = query.with_for_update()
        batch = self.db.scalar(query)
        if batch is None:
            raise ImportDraftNotFoundError("Import preview not found.")
        if batch.status != "draft":
            raise ImportReviewValidationError("Only draft imports can be edited.")
        return batch

    def _get_rows(self, import_batch_id: UUID) -> list[ImportPreviewRow]:
        return self.db.scalars(
            select(ImportPreviewRow)
            .where(ImportPreviewRow.import_batch_id == import_batch_id)
            .order_by(ImportPreviewRow.row_number)
        ).all()

    def _get_rules(self, family_id: UUID) -> list[CategorizationRule]:
        rules = (
            self.db.scalars(
                select(CategorizationRule)
                .options(
                    joinedload(CategorizationRule.category),
                    joinedload(CategorizationRule.subcategory),
                )
                .where(
                    CategorizationRule.is_active.is_(True),
                    or_(
                        CategorizationRule.family_id == family_id,
                        CategorizationRule.family_id.is_(None),
                    ),
                )
                .order_by(CategorizationRule.priority.desc(), CategorizationRule.id)
            )
            .unique()
            .all()
        )
        return [rule for rule in rules if self._rule_is_safe(rule, family_id)]

    def _rule_is_safe(self, rule: CategorizationRule, family_id: UUID) -> bool:
        if rule.flow_type is not None and rule.flow_type not in VALID_FLOW_TYPES:
            return False
        if rule.scope is not None and rule.scope not in VALID_SCOPES:
            return False
        if rule.category_id is not None:
            category = rule.category or self.db.get(Category, rule.category_id)
            if category is None or not (
                category.family_id == family_id
                or (category.family_id is None and category.is_system)
            ):
                return False
        if rule.subcategory_id is not None:
            subcategory = rule.subcategory or self.db.get(Subcategory, rule.subcategory_id)
            if subcategory is None:
                return False
            parent = subcategory.category or self.db.get(Category, subcategory.category_id)
            if parent is None or not (
                parent.family_id == family_id or (parent.family_id is None and parent.is_system)
            ):
                return False
            if rule.category_id is not None and subcategory.category_id != rule.category_id:
                return False
        return rule.rule_type in {"merchant", "bank_category", "keyword"}

    def _apply_rules(
        self,
        row: ImportPreviewRow,
        rules: list[CategorizationRule],
        family_id: UUID,
    ) -> None:
        merchant = normalize_review_text(row.merchant_name)
        description = normalize_review_text(row.description_raw)
        bank_category = normalize_review_text(row.bank_category_raw)
        matched: list[CategorizationRule] = []
        for rule in rules:
            if rule.family_id not in {None, family_id}:
                continue
            pattern = normalize_review_text(rule.pattern)
            if rule.rule_type == "merchant" and pattern and pattern == merchant:
                matched.append(rule)
            elif rule.rule_type == "bank_category":
                rule_bank_category = normalize_review_text(rule.bank_category or rule.pattern)
                if rule_bank_category and rule_bank_category == bank_category:
                    matched.append(rule)
            elif (
                rule.rule_type == "keyword"
                and pattern
                and (pattern in description or pattern in merchant)
            ):
                matched.append(rule)

        conflicts: list[str] = []
        selected: dict[str, object] = {}
        selected_priorities: dict[str, int] = {}
        for rule_field, row_field in RULE_OUTPUT_FIELDS.items():
            candidates = [
                rule for rule in matched if self._rule_output(rule, rule_field) is not None
            ]
            if not candidates:
                continue
            strongest_priority = max(rule.priority for rule in candidates)
            strongest = [rule for rule in candidates if rule.priority == strongest_priority]
            values = {self._rule_output(rule, rule_field) for rule in strongest}
            if len(values) > 1:
                conflicts.append(rule_field)
                continue
            value = next(iter(values))
            if rule_field in {"category_id", "subcategory_id"}:
                value = UUID(str(value))
            selected[row_field] = value
            selected_priorities[row_field] = strongest_priority

        selected_category = selected.get("proposed_category_id")
        selected_subcategory = selected.get("proposed_subcategory_id")
        if selected_subcategory is not None:
            subcategory = self.db.get(Subcategory, selected_subcategory)
            if subcategory is None or (
                selected_category is not None and subcategory.category_id != selected_category
            ):
                selected.pop("proposed_subcategory_id", None)
                if selected_category is None or selected_priorities.get(
                    "proposed_subcategory_id", 0
                ) >= selected_priorities.get("proposed_category_id", 0):
                    conflicts.append("subcategory_id")

        for row_field, value in selected.items():
            setattr(row, row_field, value)

        payload = dict(row.normalized_payload or {})
        payload["rule_conflict_fields"] = sorted(set(conflicts))
        payload["base_reason_codes"] = list(row.reason_codes or [])
        row.normalized_payload = payload
        self.recompute_row(row)

    def _rule_output(self, rule: CategorizationRule, field: str):
        value = getattr(rule, field)
        if field == "category_id" and value is None and rule.subcategory_id is not None:
            subcategory = rule.subcategory or self.db.get(Subcategory, rule.subcategory_id)
            return subcategory.category_id if subcategory is not None else None
        return value

    def _match_duplicates(self, family_id: UUID, rows: list[ImportPreviewRow]) -> None:
        existing = (
            self.db.scalars(
                select(Transaction)
                .options(
                    joinedload(Transaction.payment_instrument),
                    joinedload(Transaction.merchant),
                )
                .where(
                    Transaction.family_id == family_id,
                    Transaction.deleted_at.is_(None),
                )
                .order_by(Transaction.created_at, Transaction.id)
            )
            .unique()
            .all()
        )
        first_in_file: dict[tuple[object, ...], ImportPreviewRow] = {}
        for row in rows:
            payload = dict(row.normalized_payload or {})
            payload.pop("duplicate_of_row_number", None)
            row.duplicate_transaction_id = None

            existing_match = self._find_existing_duplicate(row, existing)
            if existing_match is not None:
                row.duplicate_transaction_id = existing_match.id

            file_key = self._same_file_key(row)
            if file_key is not None:
                prior = first_in_file.get(file_key)
                if prior is None:
                    first_in_file[file_key] = row
                else:
                    payload["duplicate_of_row_number"] = prior.row_number

            if row.duplicate_transaction_id is None and "duplicate_of_row_number" not in payload:
                row.duplicate_included = False
            row.normalized_payload = payload
            self.recompute_row(row)

    def _find_existing_duplicate(
        self, row: ImportPreviewRow, transactions: list[Transaction]
    ) -> Transaction | None:
        description = normalize_review_text(row.description_raw or row.merchant_name)
        currency = (row.currency or "").strip().upper()
        if row.occurred_at is None or row.amount is None or not description or not currency:
            return None
        for transaction in transactions:
            if transaction.amount != row.amount or transaction.currency.upper() != currency:
                continue
            if not self._same_occurrence(row.occurred_at, transaction.occurred_at):
                continue
            transaction_description = normalize_review_text(
                transaction.description_normalized
                or transaction.description_raw
                or (transaction.merchant.name if transaction.merchant is not None else None)
            )
            if not transaction_description or transaction_description != description:
                continue
            instrument_row = normalize_review_text(row.payment_instrument_label)
            payment_instrument = transaction.payment_instrument
            instrument_transaction = normalize_review_text(
                payment_instrument.masked_label if payment_instrument is not None else None
            )
            if (
                instrument_row
                and instrument_transaction
                and instrument_row != instrument_transaction
            ):
                continue
            return transaction
        return None

    def _same_occurrence(self, left: datetime, right: datetime) -> bool:
        # Bank exports currently carry local wall time without an offset. Compare the
        # displayed bank timestamp exactly; don't invent a timezone conversion here.
        return left.replace(tzinfo=None) == right.replace(tzinfo=None)

    def _same_file_key(self, row: ImportPreviewRow) -> tuple[object, ...] | None:
        description = normalize_review_text(row.description_raw or row.merchant_name)
        if row.occurred_at is None or row.amount is None or not description:
            return None
        return (
            row.occurred_at.replace(tzinfo=None),
            row.amount,
            (row.currency or "").strip().upper(),
            description,
            normalize_review_text(row.payment_instrument_label),
        )

    def _has_duplicate(self, row: ImportPreviewRow) -> bool:
        payload = row.normalized_payload or {}
        return (
            row.duplicate_transaction_id is not None
            or payload.get("duplicate_of_row_number") is not None
        )

    def has_duplicate(self, row: ImportPreviewRow) -> bool:
        return self._has_duplicate(row)

    def _save_rules_for_rows(self, family_id: UUID, rows: list[ImportPreviewRow]) -> None:
        grouped: dict[str, list[ImportPreviewRow]] = {}
        for row in rows:
            pattern = normalize_review_text(row.merchant_name)
            if not pattern:
                raise ImportReviewValidationError("A merchant is required to save a rule.")
            grouped.setdefault(pattern, []).append(row)

        for pattern, merchant_rows in grouped.items():
            proposals = {
                (
                    row.proposed_category_id,
                    row.proposed_subcategory_id,
                    row.proposed_flow_type,
                    row.proposed_scope,
                )
                for row in merchant_rows
            }
            if len(proposals) != 1:
                raise ImportReviewValidationError(
                    "Selected rows for the same merchant have conflicting rule outputs."
                )
            category_id, subcategory_id, flow_type, scope = next(iter(proposals))
            if all(value is None for value in (category_id, subcategory_id, flow_type, scope)):
                raise ImportReviewValidationError("The correction has no values to save as a rule.")
            if (
                category_id is not None
                and self._get_allowed_category(family_id, category_id) is None
            ):
                raise ImportReviewValidationError("Category not found in this family.")
            if subcategory_id is not None and (
                category_id is None
                or self._get_allowed_subcategory(family_id, category_id, subcategory_id) is None
            ):
                raise ImportReviewValidationError(
                    "Subcategory must belong to the selected family category."
                )

            candidates = self.db.scalars(
                select(CategorizationRule)
                .where(
                    CategorizationRule.family_id == family_id,
                    CategorizationRule.rule_type == "merchant",
                    CategorizationRule.pattern == pattern,
                )
                .order_by(
                    CategorizationRule.is_active.desc(),
                    CategorizationRule.priority.desc(),
                    CategorizationRule.id,
                )
            ).all()
            rule = (
                candidates[0]
                if candidates
                else CategorizationRule(
                    family_id=family_id,
                    rule_type="merchant",
                    pattern=pattern,
                )
            )
            if not candidates:
                self.db.add(rule)
            for redundant in candidates[1:]:
                redundant.is_active = False
            rule.category_id = category_id
            rule.subcategory_id = subcategory_id
            rule.flow_type = flow_type
            rule.scope = scope
            rule.priority = 300
            rule.is_active = True

    def _review_state(self, row: ImportPreviewRow) -> tuple[object, ...]:
        return (
            row.proposed_category_id,
            row.proposed_subcategory_id,
            row.proposed_flow_type,
            row.proposed_scope,
            row.merchant_name,
            row.status,
            tuple(row.reason_codes or []),
            row.duplicate_included,
            row.reviewed_uncategorized,
            row.reviewed_at,
            tuple((row.normalized_payload or {}).get("rule_conflict_fields", [])),
        )
