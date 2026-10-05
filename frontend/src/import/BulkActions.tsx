import { useMemo, useState } from "react";
import type { FormEvent } from "react";

import type {
  CategoryApiRow,
  ImportBulkAction,
  ImportBulkActionRequest,
  ImportFlowType,
  ImportPreviewRow,
  ImportScope,
} from "../api";
import { importCopy, interpolate } from "./importCopy";
import { buildBulkActionRequest } from "./logic";
import type { Locale } from "./types";

const actions: { value: ImportBulkAction; label: "bulkAssignCategory" | "bulkSetScope" | "bulkSetFlow" | "bulkExclude" | "bulkIncludeDuplicates" | "bulkUncategorized" | "bulkCorrection" }[] = [
  { value: "assign_category", label: "bulkAssignCategory" },
  { value: "set_scope", label: "bulkSetScope" },
  { value: "set_flow_type", label: "bulkSetFlow" },
  { value: "exclude", label: "bulkExclude" },
  { value: "include_duplicate", label: "bulkIncludeDuplicates" },
  { value: "mark_uncategorized", label: "bulkUncategorized" },
  { value: "apply_correction", label: "bulkCorrection" },
];

const flows: { value: ImportFlowType; label: "flowPurchase" | "flowCashWithdrawal" | "flowCashExpense" | "flowOwnTransfer" | "flowSavings" | "flowWifeTransfer" | "flowPersonTransfer" | "flowRequisites" | "flowRefund" | "flowIncome" | "flowSubscription" | "flowWork" | "flowOther" }[] = [
  { value: "purchase", label: "flowPurchase" },
  { value: "cash_withdrawal", label: "flowCashWithdrawal" },
  { value: "cash_expense", label: "flowCashExpense" },
  { value: "transfer_to_own_account", label: "flowOwnTransfer" },
  { value: "transfer_to_savings", label: "flowSavings" },
  { value: "transfer_to_wife", label: "flowWifeTransfer" },
  { value: "person_transfer", label: "flowPersonTransfer" },
  { value: "requisites_payment", label: "flowRequisites" },
  { value: "refund", label: "flowRefund" },
  { value: "income", label: "flowIncome" },
  { value: "subscription", label: "flowSubscription" },
  { value: "work_fop", label: "flowWork" },
  { value: "other", label: "flowOther" },
];

const scopes: { value: ImportScope; label: "scopeFamily" | "scopePersonal" | "scopeWork" }[] = [
  { value: "family", label: "scopeFamily" },
  { value: "personal_main_user", label: "scopePersonal" },
  { value: "work_fop", label: "scopeWork" },
];

export function BulkActions({
  locale,
  categories,
  selectedRows,
  busy,
  onApply,
}: {
  locale: Locale;
  categories: CategoryApiRow[];
  selectedRows: ImportPreviewRow[];
  busy: boolean;
  onApply: (payload: ImportBulkActionRequest) => void;
}) {
  const t = importCopy[locale];
  const [action, setAction] = useState<ImportBulkAction>("assign_category");
  const [categoryId, setCategoryId] = useState("");
  const [subcategoryId, setSubcategoryId] = useState("");
  const [scope, setScope] = useState("");
  const [flow, setFlow] = useState("");
  const [merchantName, setMerchantName] = useState("");
  const [applyToMerchant, setApplyToMerchant] = useState(false);
  const [saveRule, setSaveRule] = useState(false);

  const category = useMemo(() => categories.find((item) => item.id === categoryId), [categories, categoryId]);
  const canIncludeSelectedDuplicates = selectedRows.every(
    (row) => row.duplicate_transaction_id !== null || row.duplicate_of_row_number !== null,
  );

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedRows.length || (action === "include_duplicate" && !canIncludeSelectedDuplicates)) return;
    const values: Omit<ImportBulkActionRequest, "action" | "row_ids"> = {
      apply_to_merchant: applyToMerchant,
      save_rule: saveRule,
    };
    if (action === "assign_category" || action === "apply_correction") {
      if (categoryId) values.proposed_category_id = categoryId;
      if (subcategoryId) values.proposed_subcategory_id = subcategoryId;
    }
    if (scope && (action === "set_scope" || action === "apply_correction")) {
      values.proposed_scope = scope as ImportScope;
    }
    if (flow && (action === "set_flow_type" || action === "apply_correction")) {
      values.proposed_flow_type = flow as ImportFlowType;
    }
    if (action === "apply_correction" && merchantName.trim()) values.merchant_name = merchantName.trim();
    if (action === "assign_category" && !categoryId) return;
    if (action === "apply_correction" && !categoryId && !merchantName.trim() && !scope && !flow) {
      return;
    }
    onApply(buildBulkActionRequest(action, selectedRows, values));
  }

  const needsCategory = action === "assign_category" || action === "apply_correction";
  const needsScope = action === "set_scope" || action === "apply_correction";
  const needsFlow = action === "set_flow_type" || action === "apply_correction";
  const canSubmit = selectedRows.length > 0
    && !busy
    && (action !== "assign_category" || Boolean(categoryId))
    && (action !== "set_scope" || Boolean(scope))
    && (action !== "set_flow_type" || Boolean(flow))
    && (action !== "apply_correction" || Boolean(categoryId || merchantName.trim() || scope || flow))
    && (action !== "include_duplicate" || canIncludeSelectedDuplicates);

  return (
    <form className="panel bulk-actions" onSubmit={submit}>
      <div className="bulk-actions-heading">
        <div>
          <h3>{t.bulkAction}</h3>
          <p>{interpolate(t.selectedRows, { count: selectedRows.length })}</p>
        </div>
        {selectedRows.length > 0 && (
          <p className="bulk-impact-note">{interpolate(t.bulkConfirm, { count: selectedRows.length })}</p>
        )}
      </div>
      <div className="bulk-controls">
        <label className="field">
          <span>{t.bulkAction}</span>
          <select value={action} onChange={(event) => setAction(event.target.value as ImportBulkAction)}>
            {actions.map((item) => <option key={item.value} value={item.value}>{t[item.label]}</option>)}
          </select>
        </label>
        {needsCategory && (
          <>
            <label className="field">
              <span>{t.category}</span>
              <select
                value={categoryId}
                onChange={(event) => {
                  setCategoryId(event.target.value);
                  setSubcategoryId("");
                }}
              >
                <option value="">{t.chooseCategory}</option>
                {categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label className="field">
              <span>{t.chooseSubcategory}</span>
              <select disabled={!category} value={subcategoryId} onChange={(event) => setSubcategoryId(event.target.value)}>
                <option value="">{t.noSubcategory}</option>
                {category?.subcategories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
          </>
        )}
        {needsScope && (
          <label className="field">
            <span>{t.scope}</span>
            <select value={scope} onChange={(event) => setScope(event.target.value as ImportScope)}>
              <option value="">{t.scopeUnknown}</option>
              {scopes.map((item) => <option key={item.value} value={item.value}>{t[item.label]}</option>)}
            </select>
          </label>
        )}
        {needsFlow && (
          <label className="field">
            <span>{t.flow}</span>
            <select value={flow} onChange={(event) => setFlow(event.target.value as ImportFlowType)}>
              <option value="">{t.flowUnknown}</option>
              {flows.map((item) => <option key={item.value} value={item.value}>{t[item.label]}</option>)}
            </select>
          </label>
        )}
        {action === "apply_correction" && (
          <label className="field">
            <span>{t.merchantName}</span>
            <input maxLength={255} value={merchantName} onChange={(event) => setMerchantName(event.target.value)} />
          </label>
        )}
      </div>
      {(action === "apply_correction" || action === "assign_category") && (
        <div className="bulk-options">
          <label className="import-check-row">
            <input checked={applyToMerchant} onChange={(event) => setApplyToMerchant(event.target.checked)} type="checkbox" />
            <span>{t.applyToMerchant}</span>
          </label>
          <label className="import-check-row">
            <input checked={saveRule} onChange={(event) => setSaveRule(event.target.checked)} type="checkbox" />
            <span>{t.ruleSave}</span>
          </label>
        </div>
      )}
      {action === "include_duplicate" && !canIncludeSelectedDuplicates && (
        <p className="table-error" role="alert">{t.bulkError}</p>
      )}
      {action === "assign_category" && !categoryId && selectedRows.length > 0 && (
        <p className="field-help">{t.bulkNeedCategory}</p>
      )}
      <button className="primary-button" disabled={!canSubmit} type="submit">
        {busy ? t.workingBulk : t.applyBulk}
      </button>
    </form>
  );
}
