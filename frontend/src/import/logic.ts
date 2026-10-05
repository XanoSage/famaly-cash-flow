import type {
  ImportBulkAction,
  ImportBulkActionRequest,
  ImportFlowType,
  ImportPreviewRow,
  ImportPreviewRowPatch,
  ImportScope,
  ImportSummary,
} from "../api";
import type { ImportTab } from "./types";

export function recommendedImportTab(summary: ImportSummary): ImportTab {
  if (summary.error_count > 0) return "errors";
  if (summary.needs_review_count > 0) return "needs_review";
  if (summary.duplicate_count > 0) return "duplicates";
  return "all";
}

export function correctedPageOffset(offset: number, limit: number, matchingRowsCount: number) {
  if (matchingRowsCount <= 0) return 0;
  return Math.min(offset, Math.floor((matchingRowsCount - 1) / limit) * limit);
}

export function categorySelectionChanged(categoryId: string) {
  return { categoryId, subcategoryId: "", intentionalUncategorized: false };
}

export function buildImportRowPatch(values: {
  merchantName: string;
  categoryId: string;
  subcategoryId: string;
  flowType: string;
  scope: string;
  excluded: boolean;
  includeDuplicate: boolean;
  hasDuplicate: boolean;
  intentionalUncategorized: boolean;
  saveRule: boolean;
  applyToMerchant: boolean;
}): ImportPreviewRowPatch {
  const payload: ImportPreviewRowPatch = {
    merchant_name: values.merchantName,
    proposed_category_id: values.intentionalUncategorized ? null : values.categoryId || null,
    proposed_subcategory_id: values.intentionalUncategorized ? null : values.subcategoryId || null,
    proposed_flow_type: (values.flowType || null) as ImportFlowType | null,
    proposed_scope: (values.scope || null) as ImportScope | null,
    excluded: values.excluded,
    save_rule: values.saveRule,
    apply_to_merchant: values.applyToMerchant,
  };
  if (values.hasDuplicate) payload.include_duplicate = values.includeDuplicate;
  if (values.intentionalUncategorized) payload.accept_uncategorized = true;
  return payload;
}

export function buildBulkActionRequest(
  action: ImportBulkAction,
  selectedRows: ImportPreviewRow[],
  values: Omit<ImportBulkActionRequest, "action" | "row_ids">,
): ImportBulkActionRequest {
  return { action, row_ids: selectedRows.map((row) => row.id), ...values };
}

export function filterSelectedRows(rows: ImportPreviewRow[], selectedIds: Set<string>) {
  return rows.filter((row) => selectedIds.has(row.id));
}
