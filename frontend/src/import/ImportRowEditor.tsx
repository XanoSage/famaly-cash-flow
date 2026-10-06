import { useEffect, useMemo, useState } from "react";

import type {
  CategoryApiRow,
  ImportFlowType,
  ImportPreviewRow,
  ImportPreviewRowPatch,
  ImportScope,
} from "../api";
import { importCopy } from "./importCopy";
import { buildImportRowPatch, categorySelectionChanged } from "./logic";
import type { Locale } from "./types";

const flows: { value: ImportFlowType; copyKey: keyof typeof importCopy.ru }[] = [
  { value: "purchase", copyKey: "flowPurchase" },
  { value: "cash_withdrawal", copyKey: "flowCashWithdrawal" },
  { value: "cash_expense", copyKey: "flowCashExpense" },
  { value: "transfer_to_own_account", copyKey: "flowOwnTransfer" },
  { value: "transfer_to_savings", copyKey: "flowSavings" },
  { value: "transfer_to_wife", copyKey: "flowWifeTransfer" },
  { value: "person_transfer", copyKey: "flowPersonTransfer" },
  { value: "requisites_payment", copyKey: "flowRequisites" },
  { value: "refund", copyKey: "flowRefund" },
  { value: "income", copyKey: "flowIncome" },
  { value: "subscription", copyKey: "flowSubscription" },
  { value: "work_fop", copyKey: "flowWork" },
  { value: "other", copyKey: "flowOther" },
];

const scopes: { value: ImportScope; copyKey: keyof typeof importCopy.ru }[] = [
  { value: "family", copyKey: "scopeFamily" },
  { value: "personal_main_user", copyKey: "scopePersonal" },
  { value: "work_fop", copyKey: "scopeWork" },
];

export function ImportRowEditor({
  row,
  categories,
  locale,
  saving,
  onClose,
  onSave,
}: {
  row: ImportPreviewRow | null;
  categories: CategoryApiRow[];
  locale: Locale;
  saving: boolean;
  onClose: () => void;
  onSave: (payload: ImportPreviewRowPatch) => void;
}) {
  const t = importCopy[locale];
  const [merchantName, setMerchantName] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [subcategoryId, setSubcategoryId] = useState("");
  const [flowType, setFlowType] = useState("");
  const [scope, setScope] = useState("");
  const [excluded, setExcluded] = useState(false);
  const [includeDuplicate, setIncludeDuplicate] = useState(false);
  const [intentionalUncategorized, setIntentionalUncategorized] = useState(false);
  const [saveRule, setSaveRule] = useState(false);
  const [applyToMerchant, setApplyToMerchant] = useState(false);

  useEffect(() => {
    if (!row) return;
    setMerchantName(row.merchant_name ?? "");
    setCategoryId(row.proposed_category_id ?? "");
    setSubcategoryId(row.proposed_subcategory_id ?? "");
    setFlowType(row.proposed_flow_type ?? "");
    setScope(row.proposed_scope ?? "");
    setExcluded(row.status === "excluded");
    setIncludeDuplicate(row.duplicate_included);
    setIntentionalUncategorized(row.reviewed_uncategorized);
    setSaveRule(false);
    setApplyToMerchant(false);
  }, [row]);

  const selectedCategory = useMemo(
    () => categories.find((category) => category.id === categoryId),
    [categories, categoryId],
  );
  if (!row) return null;
  const hasDuplicate = row.duplicate_transaction_id !== null || row.duplicate_of_row_number !== null;

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSave(buildImportRowPatch({
      merchantName,
      categoryId,
      subcategoryId,
      flowType,
      scope,
      excluded,
      includeDuplicate,
      hasDuplicate,
      intentionalUncategorized,
      saveRule,
      applyToMerchant,
    }));
  }

  return (
    <div className="import-drawer-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !saving) onClose();
    }}>
      <aside
        aria-labelledby="import-editor-title"
        aria-modal="true"
        className="import-row-editor"
        role="dialog"
      >
        <header className="import-editor-header">
          <div>
            <p className="eyebrow">#{row.row_number}</p>
            <h2 id="import-editor-title">{row.merchant_name || row.description_raw || t.edit}</h2>
          </div>
          <button aria-label={t.close} className="icon-button" disabled={saving} onClick={onClose} type="button">×</button>
        </header>
        {row.error_message && <div className="import-inline-error"><strong>{t.errorRowTitle}</strong><p>{row.error_message}</p><span>{t.errorRowHelp}</span></div>}
        <form className="import-editor-form" onSubmit={submit}>
          <label className="field">
            <span>{t.merchantName}</span>
            <input maxLength={255} value={merchantName} onChange={(event) => setMerchantName(event.target.value)} />
          </label>
          <label className="field">
            <span>{t.category}</span>
            <select
              aria-label={t.category}
              value={categoryId}
              onChange={(event) => {
                const next = categorySelectionChanged(event.target.value);
                setCategoryId(next.categoryId);
                setSubcategoryId(next.subcategoryId);
                setIntentionalUncategorized(next.intentionalUncategorized);
              }}
            >
              <option value="">{t.chooseCategory}</option>
              {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
            </select>
          </label>
          <label className="field">
            <span>{t.category} / {t.chooseSubcategory}</span>
            <select
              aria-label={`${t.category} / ${t.chooseSubcategory}`}
              disabled={!selectedCategory}
              value={subcategoryId}
              onChange={(event) => setSubcategoryId(event.target.value)}
            >
              <option value="">{t.noSubcategory}</option>
              {selectedCategory?.subcategories.map((subcategory) => (
                <option key={subcategory.id} value={subcategory.id}>{subcategory.name}</option>
              ))}
            </select>
          </label>
          <div className="import-editor-inline-actions">
            <button
              className={`secondary-button${intentionalUncategorized ? " is-selected" : ""}`}
              onClick={() => {
                setCategoryId("");
                setSubcategoryId("");
                setIntentionalUncategorized(true);
              }}
              type="button"
            >
              {t.noCategoryAction}
            </button>
            {intentionalUncategorized && <small>{t.noCategoryHelp}</small>}
          </div>
          <label className="field">
            <span>{t.flow}</span>
            <select value={flowType} onChange={(event) => setFlowType(event.target.value)}>
              <option value="">{t.flowUnknown}</option>
              {flows.map(({ value, copyKey }) => <option key={value} value={value}>{t[copyKey]}</option>)}
            </select>
          </label>
          <label className="field">
            <span>{t.scope}</span>
            <select value={scope} onChange={(event) => setScope(event.target.value)}>
              <option value="">{t.scopeUnknown}</option>
              {scopes.map(({ value, copyKey }) => <option key={value} value={value}>{t[copyKey]}</option>)}
            </select>
          </label>
          <label className="import-check-row">
            <input checked={!excluded} onChange={(event) => setExcluded(!event.target.checked)} type="checkbox" />
            <span>{t.includeInImport}</span>
          </label>
          {hasDuplicate && (
            <label className="import-check-row import-duplicate-choice">
              <input checked={includeDuplicate} onChange={(event) => setIncludeDuplicate(event.target.checked)} type="checkbox" />
              <span>{t.includeDuplicate}</span>
            </label>
          )}
          {hasDuplicate && <p className="field-help">{includeDuplicate ? t.duplicateIncluded : t.duplicateSkipped}</p>}
          <label className="import-check-row">
            <input checked={saveRule} onChange={(event) => setSaveRule(event.target.checked)} type="checkbox" />
            <span>{t.ruleSave}</span>
          </label>
          {saveRule && <p className="field-help">{t.ruleSaveHelp}</p>}
          <label className="import-check-row">
            <input checked={applyToMerchant} disabled={!merchantName.trim()} onChange={(event) => setApplyToMerchant(event.target.checked)} type="checkbox" />
            <span>{t.applyToMerchant}</span>
          </label>
          <div className="import-editor-footer">
            <button className="secondary-button" disabled={saving} onClick={onClose} type="button">{t.close}</button>
            <button className="primary-button" disabled={saving} type="submit">{saving ? t.saving : t.save}</button>
          </div>
        </form>
      </aside>
    </div>
  );
}
