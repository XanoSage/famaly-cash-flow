import type { CategoryApiRow, ImportPreviewFilters } from "../api";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { importCopy, type ImportCopy } from "./importCopy";
import type { ImportTab, Locale } from "./types";

const tabs: { key: ImportTab; copyKey: keyof typeof importCopy.ru }[] = [
  { key: "needs_review", copyKey: "filterNeedsReview" },
  { key: "duplicates", copyKey: "filterDuplicates" },
  { key: "errors", copyKey: "filterErrors" },
  { key: "uncategorized", copyKey: "filterUncategorized" },
  { key: "ready", copyKey: "filterReady" },
  { key: "excluded", copyKey: "filterExcluded" },
  { key: "all", copyKey: "filterAll" },
];

const reasonCodes = [
  "new_merchant",
  "large_amount",
  "large_supermarket",
  "person_transfer",
  "wife_transfer",
  "requisites_payment",
  "low_confidence",
  "work_fop_candidate",
  "duplicate",
  "uncategorized",
  "rule_conflict",
  "parse_error",
];

export type AppliedImportFilters = Pick<
  ImportPreviewFilters,
  "merchant" | "bank_category" | "proposed_category_id" | "reason_code"
>;

export function ImportFilters({
  locale,
  tab,
  categories,
  matchingRowsCount,
  summaryCounts,
  filters,
  onTabChange,
  onFiltersApply,
}: {
  locale: Locale;
  tab: ImportTab;
  categories: CategoryApiRow[];
  matchingRowsCount: number;
  summaryCounts: Record<ImportTab, number>;
  filters: AppliedImportFilters;
  onTabChange: (tab: ImportTab) => void;
  onFiltersApply: (filters: AppliedImportFilters) => void;
}) {
  const t = importCopy[locale];
  const [merchant, setMerchant] = useState(filters.merchant ?? "");
  const [bankCategory, setBankCategory] = useState(filters.bank_category ?? "");
  const [categoryId, setCategoryId] = useState(filters.proposed_category_id ?? "");
  const [reasonCode, setReasonCode] = useState(filters.reason_code ?? "");

  useEffect(() => {
    setMerchant(filters.merchant ?? "");
    setBankCategory(filters.bank_category ?? "");
    setCategoryId(filters.proposed_category_id ?? "");
    setReasonCode(filters.reason_code ?? "");
  }, [filters]);

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFiltersApply({
      merchant: merchant.trim() || undefined,
      bank_category: bankCategory.trim() || undefined,
      proposed_category_id: categoryId || undefined,
      reason_code: reasonCode || undefined,
    });
  }

  function clear() {
    setMerchant("");
    setBankCategory("");
    setCategoryId("");
    setReasonCode("");
    onFiltersApply({});
  }

  return (
    <section className="import-filter-panel" aria-label={t.reviewTitle}>
      <div className="import-tabs" role="tablist" aria-label={t.reviewTitle}>
        {tabs.map(({ key, copyKey }) => (
          <button
            aria-selected={tab === key}
            className={`import-tab${tab === key ? " is-active" : ""}`}
            key={key}
            onClick={() => onTabChange(key)}
            role="tab"
            type="button"
          >
            <span>{t[copyKey]}</span>
            <b>{summaryCounts[key]}</b>
          </button>
        ))}
      </div>
      <form className="import-extra-filters" onSubmit={apply}>
        <label className="field">
          <span>{t.merchantSearch}</span>
          <input value={merchant} onChange={(event) => setMerchant(event.target.value)} />
        </label>
        <label className="field">
          <span>{t.bankCategorySearch}</span>
          <input value={bankCategory} onChange={(event) => setBankCategory(event.target.value)} />
        </label>
        <label className="field">
          <span>{t.proposedCategory}</span>
          <select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}>
            <option value="">{t.anyCategory}</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>{category.name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t.reasonFilter}</span>
          <select value={reasonCode} onChange={(event) => setReasonCode(event.target.value)}>
            <option value="">{t.anyReason}</option>
            {reasonCodes.map((code) => (
              <option key={code} value={code}>{reasonLabel(t, code)}</option>
            ))}
          </select>
        </label>
        <div className="import-filter-actions">
          <button className="primary-button" type="submit">{t.applyFilters}</button>
          <button className="secondary-button" onClick={clear} type="button">{t.clearFilters}</button>
        </div>
      </form>
      <p className="import-result-count">{t.showing}: {matchingRowsCount}</p>
    </section>
  );
}

function reasonLabel(t: ImportCopy, code: string) {
  const key = `reason_${code}` as keyof ImportCopy;
  return t[key] ?? t.reason_unknown;
}
