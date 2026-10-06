# Private Real Data Smoke Checklist

Use this checklist only in a private local environment with a real statement. GitHub Actions and the
synthetic E2E fixture must never receive real bank data. Keep the completed notes, statement, backup,
screenshots, and identifiers outside this repository; commit only the blank template below.

## Before importing

- [ ] Confirm `DATABASE_URL` points to the intended private local PostgreSQL database, not CI,
  staging, or production.
- [ ] Make and verify a database backup. Store it in an encrypted location outside the repository.
- [ ] Keep the XLSX outside the repository and confirm it is not staged or tracked by Git.
- [ ] Sign in to the Web app and verify the expected family and default bank account.
- [ ] Record the statement's private date range and the bank's expected operation count in a separate
  private copy of the validation template.

## Preview and review

- [ ] Upload the statement through the Web Import screen.
- [ ] Compare parsed row count with the bank's expected row count.
- [ ] Inspect the preview summary: ready, review, duplicate, excluded, uncategorized, and error rows.
- [ ] Inspect unknown merchants and verify their proposed category or record the correction needed.
- [ ] Inspect person transfers, transfers between own accounts, and payments by details.
- [ ] Inspect every possible duplicate against the statement and existing transactions. Record whether
  it should be skipped or explicitly included.
- [ ] Inspect incoming transactions and distinguish salary/income, refunds, own transfers, and debt.
- [ ] Inspect ATM/cash withdrawal candidates and verify they are not ordinary family expenses.
- [ ] Correct representative rows in the UI and confirm review counters update before confirmation.

## Confirm and compare

- [ ] Select the intended bank/card account and confirm the import through the Web UI.
- [ ] Compare imported and excluded counts with the expected statement rows.
- [ ] Compare income and expense totals for the statement period where currencies and bank semantics
  make a direct comparison meaningful.
- [ ] Open the dashboard and inspect total expenses, income, transfers, categories, and merchants.
- [ ] Open Transactions and spot-check the imported operation count, dates, signs, account, category,
  and review status.
- [ ] Record discrepancies without copying merchant descriptions, card details, or amounts into this
  repository.

## Manual transaction and cash checks

- [ ] Create one small, clearly identified manual expense through Web and verify its amount, sign,
  category, and dashboard effect.
- [ ] Create one card-to-cash withdrawal through the Cash screen and verify cash balance increases
  while family expenses stay unchanged.
- [ ] Record one cash expense and verify cash balance decreases while family expenses increase once.
- [ ] Reload the app and verify the transactions remain present and soft-deleted rows remain absent
  from normal lists and analytics.
- [ ] Note any timestamp offset, date-boundary, or imported bank wall-time anomalies for follow-up.

## Private validation notes template

Copy this blank table to a private local note before filling it in. Do not commit a completed version
containing real statement values.

| Measure | Expected | Observed | Follow-up |
| --- | --- | --- | --- |
| Statement operation rows |  |  |  |
| Parsed preview rows |  |  |  |
| Imported rows |  |  |  |
| Excluded rows |  |  |  |
| Possible duplicates |  |  |  |
| Uncategorized rows |  |  |  |
| Transfers/person payments |  |  |  |
| Income/refunds |  |  |  |
| Cash withdrawal candidates |  |  |  |
| Dashboard totals discrepancy |  |  |  |
| Categorization corrections needed |  |  |  |
| Timezone/date-boundary anomalies |  |  |  |

Additional private notes:

- Unknown merchants / categories:
- Duplicate decisions:
- Transfer classification gaps:
- Analytics or amount discrepancies:
- Timestamp anomalies:
- Other follow-up:
