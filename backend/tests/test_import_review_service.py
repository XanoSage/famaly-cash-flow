from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.db.seed_system_categories import seed_system_categories
from app.importers.bank_xlsx import (
    BankStatementParseResult,
    BankStatementSummary,
    ParsedBankOperation,
)
from app.models.account import Account
from app.models.categorization_rule import CategorizationRule
from app.models.category import Category, Subcategory
from app.models.family import Family
from app.models.import_batch import ImportBatch, ImportPreviewRow
from app.models.transaction import Transaction
from app.models.user import User
from app.services.confirm_import import ConfirmImportError, ConfirmImportService
from app.services.import_preview import ImportPreviewService
from app.services.import_review import ImportReviewService, ImportReviewValidationError


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
        seed_system_categories(session)
        yield session


def test_system_bank_category_rule_assigns_system_taxonomy(db_session: Session) -> None:
    seed_system_categories(db_session)
    seed_system_categories(db_session)
    system_mappings = db_session.scalars(
        select(CategorizationRule).where(
            CategorizationRule.family_id.is_(None),
            CategorizationRule.rule_type == "bank_category",
            CategorizationRule.bank_category == "Супермаркети та продукти",
        )
    ).all()
    assert len(system_mappings) == 1

    family, user = make_family_user(db_session, "system@example.com")
    batch = create_batch(db_session, family, user, [operation()])
    row = only_row(db_session, batch)
    food, groceries = system_groceries(db_session)

    assert row.proposed_category_id == food.id
    assert row.proposed_subcategory_id == groceries.id
    assert row.status == "auto_ready"


def test_family_merchant_rule_overrides_system_bank_mapping(db_session: Session) -> None:
    family, user = make_family_user(db_session, "merchant@example.com")
    custom = family_category(db_session, family, "Custom Food")
    db_session.add(
        CategorizationRule(
            family_id=family.id,
            rule_type="merchant",
            pattern="сільпо",
            category_id=custom.id,
            priority=300,
            is_active=True,
        )
    )
    db_session.commit()

    batch = create_batch(db_session, family, user, [operation(merchant="  СІЛЬПО  ")])
    row = only_row(db_session, batch)

    assert row.proposed_category_id == custom.id


def test_keyword_rule_applies_to_normalized_description(db_session: Session) -> None:
    family, user = make_family_user(db_session, "keyword@example.com")
    custom = family_category(db_session, family, "Coffee")
    db_session.add(
        CategorizationRule(
            family_id=family.id,
            rule_type="keyword",
            pattern="  Specialty   Coffee ",
            category_id=custom.id,
            flow_type="subscription",
            priority=200,
            is_active=True,
        )
    )
    db_session.commit()

    batch = create_batch(
        db_session,
        family,
        user,
        [operation(merchant="Roaster", description="SPECIALTY coffee monthly")],
    )
    row = only_row(db_session, batch)

    assert row.proposed_category_id == custom.id
    assert row.proposed_flow_type == "subscription"


def test_higher_priority_rule_wins(db_session: Session) -> None:
    family, user = make_family_user(db_session, "priority@example.com")
    lower = family_category(db_session, family, "Lower priority")
    higher = family_category(db_session, family, "Higher priority")
    db_session.add_all(
        [
            keyword_rule(family, "сільпо", lower, priority=150),
            keyword_rule(family, "market", higher, priority=250),
        ]
    )
    db_session.commit()

    batch = create_batch(db_session, family, user, [operation(description="Сільпо market")])

    assert only_row(db_session, batch).proposed_category_id == higher.id


def test_equal_priority_conflicting_rules_require_review(db_session: Session) -> None:
    family, user = make_family_user(db_session, "conflict@example.com")
    first = family_category(db_session, family, "First")
    second = family_category(db_session, family, "Second")
    db_session.add_all(
        [
            keyword_rule(family, "сільпо", first, priority=200),
            keyword_rule(family, "market", second, priority=200),
        ]
    )
    db_session.commit()

    batch = create_batch(db_session, family, user, [operation(description="Сільпо Market")])
    row = only_row(db_session, batch)

    assert row.proposed_category_id is None
    assert row.status == "needs_review"
    assert "rule_conflict" in row.reason_codes

    ImportReviewService(db_session).patch_row(
        family_id=family.id,
        import_batch_id=batch.id,
        row_id=row.id,
        changes={"proposed_category_id": first.id},
    )
    assert row.proposed_category_id == first.id
    assert row.status == "auto_ready"
    assert "rule_conflict" not in row.reason_codes


def test_equal_priority_equivalent_rules_do_not_conflict(db_session: Session) -> None:
    family, user = make_family_user(db_session, "same-rule@example.com")
    category = family_category(db_session, family, "Same output")
    db_session.add_all(
        [
            keyword_rule(family, "сільпо", category, priority=200),
            keyword_rule(family, "market", category, priority=200),
        ]
    )
    db_session.commit()

    batch = create_batch(db_session, family, user, [operation(description="Сільпо Market")])
    row = only_row(db_session, batch)

    assert row.proposed_category_id == category.id
    assert "rule_conflict" not in row.reason_codes


def test_family_rule_never_applies_to_another_family(db_session: Session) -> None:
    family_a, user_a = make_family_user(db_session, "family-a@example.com")
    family_b, user_b = make_family_user(db_session, "family-b@example.com")
    custom = family_category(db_session, family_a, "A only")
    db_session.add(
        CategorizationRule(
            family_id=family_a.id,
            rule_type="merchant",
            pattern="сільпо",
            category_id=custom.id,
            priority=300,
            is_active=True,
        )
    )
    db_session.commit()

    batch_a = create_batch(db_session, family_a, user_a, [operation()])
    batch_b = create_batch(db_session, family_b, user_b, [operation()])

    assert only_row(db_session, batch_a).proposed_category_id == custom.id
    assert only_row(db_session, batch_b).proposed_category_id == system_groceries(db_session)[0].id


def test_saved_merchant_correction_applies_to_next_import_and_is_reused(
    db_session: Session,
) -> None:
    family, user = make_family_user(db_session, "save-rule@example.com")
    custom = family_category(db_session, family, "Local Merchant Category")
    first_batch = create_batch(db_session, family, user, [operation(bank_category="Other")])
    first_row = only_row(db_session, first_batch)
    review = ImportReviewService(db_session)

    review.patch_row(
        family_id=family.id,
        import_batch_id=first_batch.id,
        row_id=first_row.id,
        changes={"proposed_category_id": custom.id},
        save_rule=True,
    )
    review.patch_row(
        family_id=family.id,
        import_batch_id=first_batch.id,
        row_id=first_row.id,
        changes={"proposed_category_id": custom.id},
        save_rule=True,
    )

    active_rules = db_session.scalars(
        select(CategorizationRule).where(
            CategorizationRule.family_id == family.id,
            CategorizationRule.rule_type == "merchant",
            CategorizationRule.pattern == "сільпо",
            CategorizationRule.is_active.is_(True),
        )
    ).all()
    assert len(active_rules) == 1

    next_batch = create_batch(db_session, family, user, [operation(bank_category="Other")])
    assert only_row(db_session, next_batch).proposed_category_id == custom.id


def test_existing_transaction_is_detected_with_duplicate_metadata(db_session: Session) -> None:
    family, user = make_family_user(db_session, "existing-duplicate@example.com")
    account = family_account(db_session, family, user)
    existing = make_transaction(family, account, operation())
    db_session.add(existing)
    db_session.commit()

    batch = create_batch(db_session, family, user, [operation()])
    row = only_row(db_session, batch)

    assert row.status == "duplicate_candidate"
    assert row.duplicate_transaction_id == existing.id
    assert "duplicate" in row.reason_codes


@pytest.mark.parametrize(
    "candidate_kind",
    ["different_merchant", "different_amount"],
)
def test_similar_date_or_amount_alone_is_not_a_duplicate(
    db_session: Session, candidate_kind: str
) -> None:
    family, user = make_family_user(db_session, "not-duplicate@example.com")
    account = family_account(db_session, family, user)
    db_session.add(make_transaction(family, account, operation()))
    db_session.commit()

    candidate = (
        operation(merchant="Different merchant", description="Different merchant")
        if candidate_kind == "different_merchant"
        else operation(amount=Decimal("-119.00"))
    )
    batch = create_batch(db_session, family, user, [candidate])
    row = only_row(db_session, batch)

    assert row.duplicate_transaction_id is None
    assert row.status == "auto_ready"


def test_same_file_repeated_row_marks_only_later_occurrence(db_session: Session) -> None:
    family, user = make_family_user(db_session, "same-file@example.com")
    batch = create_batch(db_session, family, user, [operation(), operation(row_number=4)])
    rows = db_session.scalars(
        select(ImportPreviewRow)
        .where(ImportPreviewRow.import_batch_id == batch.id)
        .order_by(ImportPreviewRow.row_number)
    ).all()

    assert rows[0].status == "auto_ready"
    assert rows[0].duplicate_transaction_id is None
    assert rows[1].status == "duplicate_candidate"
    assert rows[1].duplicate_transaction_id is None
    assert rows[1].normalized_payload["duplicate_of_row_number"] == 3


def test_duplicate_from_another_family_does_not_match(db_session: Session) -> None:
    family_a, user_a = make_family_user(db_session, "duplicate-a@example.com")
    family_b, user_b = make_family_user(db_session, "duplicate-b@example.com")
    account_b = family_account(db_session, family_b, user_b)
    db_session.add(make_transaction(family_b, account_b, operation()))
    db_session.commit()

    batch = create_batch(db_session, family_a, user_a, [operation()])
    row = only_row(db_session, batch)

    assert row.duplicate_transaction_id is None
    assert row.status == "auto_ready"


def test_untouched_duplicate_is_excluded_during_confirmation(db_session: Session) -> None:
    family, user = make_family_user(db_session, "skip-duplicate@example.com")
    account = family_account(db_session, family, user)
    db_session.add(make_transaction(family, account, operation()))
    db_session.commit()
    batch = create_batch(db_session, family, user, [operation()])

    created = ConfirmImportService(db_session).confirm(
        family_id=family.id,
        import_batch_id=batch.id,
        account_id=account.id,
    )

    assert created == []
    assert (
        db_session.scalar(select(Transaction).where(Transaction.import_batch_id == batch.id))
        is None
    )
    assert batch.status == "confirmed"
    assert batch.duplicate_count == 1


def test_explicitly_included_duplicate_is_confirmed(db_session: Session) -> None:
    family, user = make_family_user(db_session, "include-duplicate@example.com")
    account = family_account(db_session, family, user)
    db_session.add(make_transaction(family, account, operation()))
    db_session.commit()
    batch = create_batch(db_session, family, user, [operation()])
    row = only_row(db_session, batch)

    ImportReviewService(db_session).bulk_action(
        family_id=family.id,
        import_batch_id=batch.id,
        row_ids=[row.id],
        action="include_duplicate",
        values={},
    )
    created = ConfirmImportService(db_session).confirm(
        family_id=family.id,
        import_batch_id=batch.id,
        account_id=account.id,
    )

    assert len(created) == 1
    assert created[0].is_duplicate_candidate is True


def test_patch_category_and_subcategory(db_session: Session) -> None:
    family, user = make_family_user(db_session, "patch-category@example.com")
    category = family_category(db_session, family, "Family category", subcategory_name="Details")
    subcategory = db_session.scalar(
        select(Subcategory).where(Subcategory.category_id == category.id)
    )
    assert subcategory is not None
    batch = create_batch(db_session, family, user, [operation(bank_category="Other")])
    row = only_row(db_session, batch)

    result = ImportReviewService(db_session).patch_row(
        family_id=family.id,
        import_batch_id=batch.id,
        row_id=row.id,
        changes={
            "proposed_category_id": category.id,
            "proposed_subcategory_id": subcategory.id,
            "proposed_flow_type": "subscription",
            "proposed_scope": "work_fop",
        },
    )

    assert result.rows[0].proposed_category_id == category.id
    assert result.rows[0].proposed_subcategory_id == subcategory.id
    assert result.rows[0].status == "auto_ready"

    account = family_account(db_session, family, user)
    created = ConfirmImportService(db_session).confirm(
        family_id=family.id,
        import_batch_id=batch.id,
        account_id=account.id,
    )
    assert created[0].category_id == category.id
    assert created[0].subcategory_id == subcategory.id
    assert created[0].flow_type == "subscription"
    assert created[0].scope == "work_fop"


def test_invalid_subcategory_and_foreign_family_category_are_rejected(db_session: Session) -> None:
    family_a, user_a = make_family_user(db_session, "edit-a@example.com")
    family_b, _ = make_family_user(db_session, "edit-b@example.com")
    category_a = family_category(db_session, family_a, "A category", subcategory_name="A sub")
    category_b = family_category(db_session, family_b, "B category", subcategory_name="B sub")
    subcategory_b = db_session.scalar(
        select(Subcategory).where(Subcategory.category_id == category_b.id)
    )
    batch = create_batch(db_session, family_a, user_a, [operation(bank_category="Other")])
    row = only_row(db_session, batch)
    review = ImportReviewService(db_session)

    with pytest.raises(ImportReviewValidationError, match="Category not found"):
        review.patch_row(
            family_id=family_a.id,
            import_batch_id=batch.id,
            row_id=row.id,
            changes={"proposed_category_id": category_b.id},
        )
    with pytest.raises(ImportReviewValidationError, match="belong"):
        review.patch_row(
            family_id=family_a.id,
            import_batch_id=batch.id,
            row_id=row.id,
            changes={
                "proposed_category_id": category_a.id,
                "proposed_subcategory_id": subcategory_b.id,
            },
        )


def test_scope_and_flow_edits_and_exclusion_of_parse_error(db_session: Session) -> None:
    family, user = make_family_user(db_session, "review-values@example.com")
    batch = create_batch(
        db_session, family, user, [operation(bank_category="Other"), parse_error()]
    )
    rows = db_session.scalars(
        select(ImportPreviewRow)
        .where(ImportPreviewRow.import_batch_id == batch.id)
        .order_by(ImportPreviewRow.row_number)
    ).all()
    review = ImportReviewService(db_session)
    review.patch_row(
        family_id=family.id,
        import_batch_id=batch.id,
        row_id=rows[0].id,
        changes={"proposed_scope": "work_fop", "proposed_flow_type": "subscription"},
    )
    review.patch_row(
        family_id=family.id,
        import_batch_id=batch.id,
        row_id=rows[1].id,
        changes={"excluded": True},
    )

    db_session.refresh(batch)
    assert rows[0].proposed_scope == "work_fop"
    assert rows[0].proposed_flow_type == "subscription"
    assert rows[0].status == "needs_review"  # category is still unresolved
    assert rows[1].status == "excluded"
    assert batch.error_count == 0
    with pytest.raises(ImportReviewValidationError, match="Invalid scope"):
        review.patch_row(
            family_id=family.id,
            import_batch_id=batch.id,
            row_id=rows[0].id,
            changes={"proposed_scope": "foreign"},
        )


def test_explicit_uncategorized_row_is_ready_and_imports_without_category(
    db_session: Session,
) -> None:
    family, user = make_family_user(db_session, "uncategorized@example.com")
    account = family_account(db_session, family, user)
    batch = create_batch(db_session, family, user, [operation()])
    row = only_row(db_session, batch)

    ImportReviewService(db_session).patch_row(
        family_id=family.id,
        import_batch_id=batch.id,
        row_id=row.id,
        changes={"accept_uncategorized": True},
    )
    assert row.proposed_category_id is None
    assert row.reviewed_uncategorized is True
    assert row.status == "auto_ready"
    assert "uncategorized" not in row.reason_codes

    created = ConfirmImportService(db_session).confirm(
        family_id=family.id,
        import_batch_id=batch.id,
        account_id=account.id,
    )
    assert len(created) == 1
    assert created[0].category_id is None


def test_bulk_assign_and_merchant_wide_corrections_recompute_counters(
    db_session: Session,
) -> None:
    family, user = make_family_user(db_session, "bulk@example.com")
    category = family_category(db_session, family, "Bulk category")
    batch = create_batch(
        db_session,
        family,
        user,
        [
            operation(row_number=3),
            operation(
                row_number=4,
                merchant="СІЛЬПО",
                description="СІЛЬПО",
                amount=Decimal("-119.00"),
            ),
        ],
    )
    rows = db_session.scalars(
        select(ImportPreviewRow)
        .where(ImportPreviewRow.import_batch_id == batch.id)
        .order_by(ImportPreviewRow.row_number)
    ).all()

    result = ImportReviewService(db_session).bulk_action(
        family_id=family.id,
        import_batch_id=batch.id,
        row_ids=[rows[0].id],
        action="assign_category",
        values={"proposed_category_id": category.id},
        apply_to_merchant=True,
    )
    db_session.refresh(batch)

    assert result.requested_count == 1
    assert result.matched_count == 2
    assert result.changed_count == 2
    assert all(row.proposed_category_id == category.id for row in rows)
    assert batch.uncategorized_count == 0
    assert batch.auto_ready_count == 2
    assert batch.needs_review_count == 0
    assert batch.imported_count == 2


def test_bulk_exclude_include_duplicate_and_foreign_row_ids(db_session: Session) -> None:
    family, user = make_family_user(db_session, "bulk-actions@example.com")
    account = family_account(db_session, family, user)
    existing = make_transaction(family, account, operation())
    db_session.add(existing)
    db_session.commit()
    batch = create_batch(db_session, family, user, [operation(), operation(row_number=4)])
    rows = db_session.scalars(
        select(ImportPreviewRow)
        .where(ImportPreviewRow.import_batch_id == batch.id)
        .order_by(ImportPreviewRow.row_number)
    ).all()
    review = ImportReviewService(db_session)

    review.bulk_action(
        family_id=family.id,
        import_batch_id=batch.id,
        row_ids=[rows[0].id],
        action="include_duplicate",
        values={},
    )
    review.bulk_action(
        family_id=family.id,
        import_batch_id=batch.id,
        row_ids=[rows[1].id],
        action="exclude",
        values={},
    )
    second_batch = create_batch(db_session, family, user, [operation(row_number=5)])
    foreign_row = only_row(db_session, second_batch)
    with pytest.raises(ImportReviewValidationError, match="do not belong"):
        review.bulk_action(
            family_id=family.id,
            import_batch_id=batch.id,
            row_ids=[foreign_row.id],
            action="exclude",
            values={},
        )

    db_session.refresh(batch)
    assert rows[0].duplicate_included is True
    assert rows[0].status == "auto_ready"
    assert rows[1].status == "excluded"
    assert batch.excluded_count == 1
    assert batch.duplicate_count == 2


def test_edits_are_draft_only_and_confirmation_is_idempotent(db_session: Session) -> None:
    family, user = make_family_user(db_session, "draft-only@example.com")
    account = family_account(db_session, family, user)
    batch = create_batch(db_session, family, user, [operation()])
    row = only_row(db_session, batch)
    review = ImportReviewService(db_session)
    review.patch_row(
        family_id=family.id,
        import_batch_id=batch.id,
        row_id=row.id,
        changes={"accept_uncategorized": True},
    )

    first = ConfirmImportService(db_session).confirm(
        family_id=family.id,
        import_batch_id=batch.id,
        account_id=account.id,
    )
    assert len(first) == 1
    with pytest.raises(ConfirmImportError, match="Only draft"):
        ConfirmImportService(db_session).confirm(
            family_id=family.id,
            import_batch_id=batch.id,
            account_id=account.id,
        )
    with pytest.raises(ImportReviewValidationError, match="Only draft"):
        review.patch_row(
            family_id=family.id,
            import_batch_id=batch.id,
            row_id=row.id,
            changes={"proposed_scope": "family"},
        )
    assert db_session.scalar(select(Transaction).where(Transaction.import_batch_id == batch.id))
    assert (
        len(
            db_session.scalars(
                select(Transaction).where(Transaction.import_batch_id == batch.id)
            ).all()
        )
        == 1
    )


def test_unresolved_error_blocks_confirmation_but_excluded_error_does_not(
    db_session: Session,
) -> None:
    family, user = make_family_user(db_session, "error-row@example.com")
    account = family_account(db_session, family, user)
    batch = create_batch(db_session, family, user, [parse_error()])
    with pytest.raises(ConfirmImportError, match="error rows"):
        ConfirmImportService(db_session).confirm(
            family_id=family.id,
            import_batch_id=batch.id,
            account_id=account.id,
        )

    row = only_row(db_session, batch)
    ImportReviewService(db_session).patch_row(
        family_id=family.id,
        import_batch_id=batch.id,
        row_id=row.id,
        changes={"excluded": True},
    )
    assert (
        ConfirmImportService(db_session).confirm(
            family_id=family.id,
            import_batch_id=batch.id,
            account_id=account.id,
        )
        == []
    )


def make_family_user(db: Session, email: str) -> tuple[Family, User]:
    family = Family(name=email)
    user = User(family=family, email=email, password_hash="hash", display_name="Owner")
    db.add_all([family, user])
    db.commit()
    return family, user


def family_account(db: Session, family: Family, user: User) -> Account:
    account = Account(
        family=family,
        owner_user=user,
        type="card",
        name="Main card",
        currency="UAH",
    )
    db.add(account)
    db.commit()
    return account


def family_category(
    db: Session,
    family: Family,
    name: str,
    *,
    subcategory_name: str | None = None,
) -> Category:
    category = Category(family_id=family.id, name=name, is_system=False)
    db.add(category)
    db.flush()
    if subcategory_name:
        db.add(Subcategory(category_id=category.id, name=subcategory_name, is_system=False))
    db.commit()
    return category


def system_groceries(db: Session) -> tuple[Category, Subcategory]:
    category = db.scalar(
        select(Category).where(Category.family_id.is_(None), Category.name == "Еда")
    )
    assert category is not None
    subcategory = db.scalar(
        select(Subcategory).where(
            Subcategory.category_id == category.id,
            Subcategory.name == "Супермаркеты",
        )
    )
    assert subcategory is not None
    return category, subcategory


def keyword_rule(family: Family, pattern: str, category: Category, *, priority: int):
    return CategorizationRule(
        family_id=family.id,
        rule_type="keyword",
        pattern=pattern,
        category_id=category.id,
        priority=priority,
        is_active=True,
    )


def operation(
    *,
    row_number: int = 3,
    merchant: str = "Сільпо",
    description: str | None = None,
    bank_category: str = "Супермаркети та продукти",
    amount: Decimal = Decimal("-118.02"),
) -> ParsedBankOperation:
    return ParsedBankOperation(
        row_number=row_number,
        status="auto_ready",
        reason_codes=[],
        occurred_at=datetime(2026, 5, 8, 15, 25),
        amount=amount,
        currency="UAH",
        transaction_amount=abs(amount),
        transaction_currency="UAH",
        balance_after=Decimal("6248.97"),
        payment_instrument_label="4627 **** **** 3421",
        bank_category_raw=bank_category,
        description_raw=description if description is not None else merchant,
        merchant_name=merchant,
        proposed_flow_type="purchase",
        proposed_scope="family",
        confidence=Decimal("0.9000"),
        error_message=None,
        normalized_payload={"direction": "expense"},
    )


def parse_error() -> ParsedBankOperation:
    return ParsedBankOperation(
        row_number=8,
        status="error",
        reason_codes=["parse_error"],
        occurred_at=None,
        amount=None,
        currency=None,
        transaction_amount=None,
        transaction_currency=None,
        balance_after=None,
        payment_instrument_label=None,
        bank_category_raw=None,
        description_raw=None,
        merchant_name=None,
        proposed_flow_type=None,
        proposed_scope=None,
        confidence=None,
        error_message="date is empty",
        normalized_payload={},
    )


def make_transaction(family: Family, account: Account, parsed: ParsedBankOperation) -> Transaction:
    normalized = (parsed.description_raw or "").casefold()
    return Transaction(
        family_id=family.id,
        account_id=account.id,
        occurred_at=parsed.occurred_at,
        amount=parsed.amount,
        currency=parsed.currency or "UAH",
        transaction_amount=parsed.transaction_amount,
        transaction_currency=parsed.transaction_currency,
        direction="expense",
        flow_type=parsed.proposed_flow_type or "purchase",
        scope=parsed.proposed_scope or "family",
        description_raw=parsed.description_raw,
        description_normalized=normalized,
    )


def create_batch(
    db: Session,
    family: Family,
    user: User,
    rows: list[ParsedBankOperation],
) -> ImportBatch:
    summary = BankStatementSummary(
        period_start=datetime(2026, 5, 1),
        period_end=datetime(2026, 5, 31),
        total_rows=len(rows),
        auto_ready_count=len(rows),
        needs_review_count=0,
        imported_count=len(rows),
        excluded_count=0,
        duplicate_count=0,
        error_count=0,
        uncategorized_count=0,
        work_fop_count=0,
        savings_count=0,
        parser_version="test-parser",
        mapping_version="test-mapping",
    )
    parsed = BankStatementParseResult(
        source_filename="synthetic.xlsx",
        sheet_name="Виписки",
        summary=summary,
        rows=rows,
    )
    return ImportPreviewService(db).create_from_parsed_statement(
        family_id=family.id,
        uploaded_by_user_id=user.id,
        parsed_statement=parsed,
    )


def only_row(db: Session, batch: ImportBatch) -> ImportPreviewRow:
    row = db.scalar(select(ImportPreviewRow).where(ImportPreviewRow.import_batch_id == batch.id))
    assert row is not None
    return row
