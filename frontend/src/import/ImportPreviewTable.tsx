import { useMemo } from "react";

import type { ImportPreviewRow } from "../api";
import { importCopy, interpolate } from "./importCopy";
import type { ImportCopy } from "./importCopy";
import type { Locale } from "./types";

export function ImportPreviewTable({
  locale,
  rows,
  selectedIds,
  savingRowId,
  onToggleRow,
  onEdit,
  onExclude,
}: {
  locale: Locale;
  rows: ImportPreviewRow[];
  selectedIds: Set<string>;
  savingRowId: string | null;
  onToggleRow: (rowId: string) => void;
  onEdit: (row: ImportPreviewRow) => void;
  onExclude: (row: ImportPreviewRow) => void;
}) {
  const t = importCopy[locale];
  const formatter = useMemo(
    () => new Intl.NumberFormat(locale === "uk" ? "uk-UA" : "ru-UA", { maximumFractionDigits: 2 }),
    [locale],
  );

  if (rows.length === 0) return <div className="import-empty-rows">{t.noRows}</div>;

  return (
    <div className="import-row-list">
      {rows.map((row) => {
        const description = row.description_raw?.trim() || "";
        const title = row.merchant_name || description || `#${row.row_number}`;
        const duplicate = row.matched_duplicate;
        return (
          <article className={`import-row-card status-${row.status}`} key={row.id}>
            <div className="import-row-topline">
              <label className="import-row-select">
                <input
                  aria-label={`${t.selectPage}: ${title}`}
                  checked={selectedIds.has(row.id)}
                  onChange={() => onToggleRow(row.id)}
                  type="checkbox"
                />
                <span>#{row.row_number}</span>
              </label>
              <div className="import-badges">
                <span className={`status-badge badge-${row.status}`}>{statusLabel(t, row.status)}</span>
                {row.reviewed_uncategorized && (
                  <span className="status-badge badge-uncategorized">{t.statusUncategorized}</span>
                )}
                {row.duplicate_included && (
                  <span className="status-badge badge-duplicate-included">{t.duplicateIncluded}</span>
                )}
                {row.proposed_scope === "work_fop" && (
                  <span className="status-badge badge-work">{t.statusWork}</span>
                )}
              </div>
              <time>{row.occurred_at ? formatDateTime(row.occurred_at, locale) : "—"}</time>
              <strong className={amountTone(row.amount)}>
                {row.amount === null ? "—" : `${formatter.format(Number(row.amount))} ${row.currency ?? ""}`}
              </strong>
            </div>
            <div className="import-row-content">
              <div className="import-row-main">
                <h3>{title}</h3>
                {description && description !== title && (
                  <p className="import-row-description" title={description}>{description}</p>
                )}
                {description.length > 100 && (
                  <details className="import-description-details">
                    <summary>{t.description}</summary>
                    <p>{description}</p>
                  </details>
                )}
                <p className="import-row-secondary">
                  {t.category}: {row.proposed_category_name ?? t.statusUncategorized}
                  {row.proposed_subcategory_name ? ` / ${row.proposed_subcategory_name}` : ""}
                </p>
                {row.bank_category_raw && (
                  <p className="import-row-secondary">{t.bankCategory}: {row.bank_category_raw}</p>
                )}
                <p className="import-row-secondary">
                  {t.flow}: {flowLabel(t, row.proposed_flow_type)} · {t.scope}: {scopeLabel(t, row.proposed_scope)}
                </p>
                {row.reason_codes.length > 0 && (
                  <div className="import-reasons" aria-label={t.reasons}>
                    {row.reason_codes.map((code) => <span key={code}>{reasonLabel(t, code)}</span>)}
                  </div>
                )}
                {row.error_message && (
                  <div className="import-inline-error" role="alert">
                    <strong>{t.errorRowTitle}</strong>
                    <p>{row.error_message}</p>
                    <span>{t.errorRowHelp}</span>
                  </div>
                )}
              </div>
              <div className="import-row-actions">
                <button className="secondary-button" onClick={() => onEdit(row)} type="button">
                  {t.edit}
                </button>
                {row.status === "error" && (
                  <button
                    className="danger-button"
                    disabled={savingRowId === row.id}
                    onClick={() => onExclude(row)}
                    type="button"
                  >
                    {savingRowId === row.id ? t.saving : t.excludeFromImport}
                  </button>
                )}
              </div>
            </div>
            {duplicate && (
              <section className="duplicate-comparison" aria-label={t.matchedTransaction}>
                <div>
                  <span>{t.incomingTransaction}</span>
                  <strong>{row.merchant_name || description || "—"}</strong>
                  <small>{row.amount ?? "—"} {row.currency} · {row.occurred_at ? formatDateTime(row.occurred_at, locale) : "—"}</small>
                </div>
                <div className="duplicate-divider" aria-hidden="true">↔</div>
                <div>
                  <span>{t.matchedTransaction}</span>
                  <strong>{duplicate.merchant_name || duplicate.description || "—"}</strong>
                  <small>{duplicate.amount} {duplicate.currency} · {formatDateTime(duplicate.occurred_at, locale)}</small>
                  {duplicate.category_name && <small>{t.category}: {duplicate.category_name}</small>}
                </div>
              </section>
            )}
            {row.duplicate_of_row_number !== null && (
              <p className="duplicate-note">
                {interpolate(t.sameFileDuplicate, { row: row.duplicate_of_row_number })}
              </p>
            )}
          </article>
        );
      })}
    </div>
  );
}

function statusLabel(t: ImportCopy, status: ImportPreviewRow["status"]) {
  const names: Record<ImportPreviewRow["status"], string> = {
    auto_ready: t.statusReady,
    needs_review: t.statusNeedsReview,
    duplicate_candidate: t.statusDuplicate,
    error: t.statusError,
    excluded: t.statusExcluded,
  };
  return names[status];
}

function reasonLabel(t: ImportCopy, code: string) {
  const key = `reason_${code}` as keyof ImportCopy;
  return t[key] ?? t.reason_unknown;
}

function flowLabel(t: ImportCopy, flow: string | null) {
  const keys: Record<string, keyof ImportCopy> = {
    purchase: "flowPurchase",
    cash_withdrawal: "flowCashWithdrawal",
    cash_expense: "flowCashExpense",
    transfer_to_own_account: "flowOwnTransfer",
    transfer_to_savings: "flowSavings",
    transfer_to_wife: "flowWifeTransfer",
    person_transfer: "flowPersonTransfer",
    requisites_payment: "flowRequisites",
    refund: "flowRefund",
    income: "flowIncome",
    subscription: "flowSubscription",
    work_fop: "flowWork",
    other: "flowOther",
  };
  return flow && keys[flow] ? t[keys[flow]] : t.flowUnknown;
}

function scopeLabel(t: ImportCopy, scope: string | null) {
  if (scope === "family") return t.scopeFamily;
  if (scope === "personal_main_user") return t.scopePersonal;
  if (scope === "work_fop") return t.scopeWork;
  return t.scopeUnknown;
}

function formatDateTime(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "uk" ? "uk-UA" : "ru-UA", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function amountTone(value: string | null) {
  if (value?.startsWith("-")) return "import-amount-negative";
  if (value && value !== "0" && value !== "0.00") return "import-amount-positive";
  return "";
}
