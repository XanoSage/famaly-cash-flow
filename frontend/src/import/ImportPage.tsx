import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  confirmImport,
  executeImportBulkAction,
  getAccounts,
  getCategories,
  getImportPreview,
  patchImportPreviewRow,
  uploadImportPreview,
  type Account,
  type CategoryApiRow,
  type ConfirmImportResponse,
  type ImportBulkActionRequest,
  type ImportPreviewFilters,
  type ImportPreviewResponse,
  type ImportPreviewRow,
  type ImportPreviewRowPatch,
  type ImportSummary,
} from "../api";
import { BulkActions } from "./BulkActions";
import { importCopy, interpolate } from "./importCopy";
import { ImportConfirmation, ImportConfirmed } from "./ImportConfirmation";
import { ImportFilters, type AppliedImportFilters } from "./ImportFilters";
import { correctedPageOffset, filterSelectedRows, recommendedImportTab } from "./logic";
import { ImportPreviewTable } from "./ImportPreviewTable";
import { ImportRowEditor } from "./ImportRowEditor";
import { ImportSummary as ImportSummaryPanel } from "./ImportSummary";
import { ImportUploader } from "./ImportUploader";
import type { ImportTab, Locale } from "./types";

const PAGE_SIZE = 50;

export function ImportPage({
  locale,
  batchId,
  onBatchIdChange,
  onAuthFailure,
  onGoDashboard,
}: {
  locale: Locale;
  batchId?: string;
  onBatchIdChange: (batchId?: string) => void;
  onAuthFailure: (error: unknown) => void;
  onGoDashboard: () => void;
}) {
  const t = importCopy[locale];
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [pageLoading, setPageLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [categories, setCategories] = useState<CategoryApiRow[]>([]);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountsLoading, setAccountsLoading] = useState(false);
  const [accountsError, setAccountsError] = useState<string | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [accountListLoaded, setAccountListLoaded] = useState(false);
  const [tab, setTab] = useState<ImportTab>("all");
  const [filters, setFilters] = useState<AppliedImportFilters>({});
  const [offset, setOffset] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [editingRow, setEditingRow] = useState<ImportPreviewRow | null>(null);
  const [savingRowId, setSavingRowId] = useState<string | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [confirmResult, setConfirmResult] = useState<ConfirmImportResponse | null>(null);
  const [duplicateSkippedCount, setDuplicateSkippedCount] = useState(0);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const requestSequence = useRef(0);

  const duplicateFilter: ImportPreviewFilters = useMemo(
    () => ({ row_status: "duplicate_candidate", offset: 0, limit: 1 }),
    [],
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const result = await getCategories();
        if (!cancelled) {
          setCategories(result.rows);
          setCategoriesError(null);
        }
      } catch (error) {
        if (!cancelled) {
          onAuthFailure(error);
          setCategoriesError(error instanceof TypeError ? t.requestError : errorMessage(error, t.categoryLoadError));
        }
      }
    })();
    return () => { cancelled = true; };
  }, [onAuthFailure, t.categoryLoadError, t.requestError]);

  const loadPage = useCallback(async (
    currentBatchId: string,
    nextOffset: number,
    nextTab: ImportTab,
    nextFilters: AppliedImportFilters,
  ) => {
    const sequence = ++requestSequence.current;
    setPageLoading(true);
    setPageError(null);
    try {
      let result = await getImportPreview(currentBatchId, apiFilters(nextTab, nextFilters, nextOffset));
      const correctedOffset = correctedPageOffset(
        result.summary.offset,
        result.summary.limit,
        result.summary.matching_rows_count,
      );
      if (correctedOffset !== result.summary.offset) {
        result = await getImportPreview(
          currentBatchId,
          apiFilters(nextTab, nextFilters, correctedOffset),
        );
      }
      const duplicateResult = await getImportPreview(currentBatchId, duplicateFilter);
      if (sequence !== requestSequence.current) return;
      setPreview(result);
      setDuplicateSkippedCount(duplicateResult.summary.matching_rows_count);
      setOffset(result.summary.offset);
    } catch (error) {
      if (sequence !== requestSequence.current) return;
      onAuthFailure(error);
      setPageError(error instanceof TypeError ? t.requestError : errorMessage(error, t.previewError));
    } finally {
      if (sequence === requestSequence.current) setPageLoading(false);
    }
  }, [duplicateFilter, onAuthFailure, t.previewError, t.requestError]);

  useEffect(() => {
    let cancelled = false;
    if (!batchId) {
      requestSequence.current += 1;
      setPreview(null);
      setPageError(null);
      setConfirmResult(null);
      setAccounts([]);
      setAccountsError(null);
      setAccountListLoaded(false);
      setSelectedAccountId("");
      setTab("all");
      setOffset(0);
      setFilters({});
      setSelectedIds(new Set());
      setPageLoading(false);
      return () => { cancelled = true; };
    }

    const sequence = ++requestSequence.current;
    setPageLoading(true);
    setPageError(null);
    setConfirmResult(null);
    setSelectedIds(new Set());
    void (async () => {
      try {
        const unfiltered = await getImportPreview(batchId, { offset: 0, limit: PAGE_SIZE });
        if (cancelled || sequence !== requestSequence.current) return;
        const defaultTab = recommendedImportTab(unfiltered.summary);
        setTab(defaultTab);
        setFilters({});
        if (defaultTab === "all") {
          setPreview(unfiltered);
          setOffset(0);
          const duplicateResult = await getImportPreview(batchId, duplicateFilter);
          if (cancelled || sequence !== requestSequence.current) return;
          setDuplicateSkippedCount(duplicateResult.summary.matching_rows_count);
          return;
        }
        const [filtered, duplicateResult] = await Promise.all([
          getImportPreview(batchId, apiFilters(defaultTab, {}, 0)),
          getImportPreview(batchId, duplicateFilter),
        ]);
        if (cancelled || sequence !== requestSequence.current) return;
        setPreview(filtered);
        setOffset(filtered.summary.offset);
        setDuplicateSkippedCount(duplicateResult.summary.matching_rows_count);
      } catch (error) {
        if (!cancelled && sequence === requestSequence.current) {
          onAuthFailure(error);
          setPageError(error instanceof TypeError ? t.requestError : errorMessage(error, t.previewError));
        }
      } finally {
        if (!cancelled && sequence === requestSequence.current) setPageLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [batchId, duplicateFilter, onAuthFailure, t.previewError, t.requestError]);

  useEffect(() => {
    if (!batchId || !preview || preview.summary.status !== "draft" || accountListLoaded) return;
    let cancelled = false;
    setAccountsLoading(true);
    setAccountsError(null);
    void (async () => {
      try {
        const result = await getAccounts();
        if (cancelled) return;
        setAccounts(result.rows);
        const preferred = result.rows.find((account) => account.is_default) ??
          (result.rows.length === 1 ? result.rows[0] : undefined);
        setSelectedAccountId(preferred?.id ?? "");
        setAccountListLoaded(true);
      } catch (error) {
        if (cancelled) return;
        onAuthFailure(error);
        setAccountsError(error instanceof TypeError ? t.requestError : errorMessage(error, t.accountsError));
        setAccountListLoaded(true);
      } finally {
        if (!cancelled) setAccountsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [accountListLoaded, batchId, onAuthFailure, preview, t.accountsError, t.requestError]);

  async function handleUpload(file: File) {
    setUploading(true);
    setUploadError(null);
    try {
      const result = await uploadImportPreview(file, PAGE_SIZE);
      setPreview(result);
      setTab(recommendedImportTab(result.summary));
      setFilters({});
      setOffset(0);
      setConfirmResult(null);
      setActionNotice(null);
      onBatchIdChange(result.summary.import_batch_id);
    } catch (error) {
      onAuthFailure(error);
      setUploadError(error instanceof TypeError ? t.requestError : errorMessage(error, t.uploadError));
    } finally {
      setUploading(false);
    }
  }

  async function handleRowSave(payload: ImportPreviewRowPatch) {
    if (!batchId || !editingRow) return;
    setSavingRowId(editingRow.id);
    setPageError(null);
    setActionNotice(null);
    try {
      const result = await patchImportPreviewRow(batchId, editingRow.id, payload);
      setActionNotice(interpolate(t.changedRows, { count: result.changed_count }));
      setEditingRow(null);
      setSelectedIds(new Set());
      await loadPage(batchId, offset, tab, filters);
    } catch (error) {
      onAuthFailure(error);
      setPageError(error instanceof TypeError ? t.requestError : errorMessage(error, t.rowSaveError));
    } finally {
      setSavingRowId(null);
    }
  }

  async function excludeRow(row: ImportPreviewRow) {
    if (!batchId) return;
    setSavingRowId(row.id);
    setActionNotice(null);
    try {
      const result = await patchImportPreviewRow(batchId, row.id, { excluded: true });
      setActionNotice(interpolate(t.changedRows, { count: result.changed_count }));
      await loadPage(batchId, offset, tab, filters);
    } catch (error) {
      onAuthFailure(error);
      setPageError(error instanceof TypeError ? t.requestError : errorMessage(error, t.rowSaveError));
    } finally {
      setSavingRowId(null);
    }
  }

  async function applyBulkAction(payload: ImportBulkActionRequest) {
    if (!batchId) return;
    setBulkBusy(true);
    setActionNotice(null);
    try {
      const result = await executeImportBulkAction(batchId, payload);
      setActionNotice(interpolate(t.changedRows, { count: result.changed_count }));
      setSelectedIds(new Set());
      await loadPage(batchId, offset, tab, filters);
    } catch (error) {
      onAuthFailure(error);
      setPageError(error instanceof TypeError ? t.requestError : errorMessage(error, t.bulkError));
    } finally {
      setBulkBusy(false);
    }
  }

  async function handleConfirm() {
    if (!batchId || !selectedAccountId || !preview || preview.summary.error_count > 0) return;
    setConfirming(true);
    setConfirmError(null);
    try {
      const result = await confirmImport(batchId, selectedAccountId);
      setConfirmResult(result);
      setPreview((current) => current ? {
        ...current,
        summary: {
          ...current.summary,
          status: result.status,
          imported_count: result.created_transactions,
          excluded_count: result.excluded_count,
          duplicate_count: result.duplicate_count,
          error_count: result.error_count,
          uncategorized_count: result.uncategorized_count,
          work_fop_count: result.work_fop_count,
          savings_count: result.savings_count,
        },
      } : current);
    } catch (error) {
      onAuthFailure(error);
      setConfirmError(error instanceof TypeError ? t.requestError : errorMessage(error, t.confirmError));
    } finally {
      setConfirming(false);
    }
  }

  function changeTab(nextTab: ImportTab) {
    if (!batchId) return;
    setTab(nextTab);
    setOffset(0);
    setSelectedIds(new Set());
    setActionNotice(null);
    void loadPage(batchId, 0, nextTab, filters);
  }

  function applyFilters(nextFilters: AppliedImportFilters) {
    if (!batchId) return;
    setFilters(nextFilters);
    setOffset(0);
    setSelectedIds(new Set());
    setActionNotice(null);
    void loadPage(batchId, 0, tab, nextFilters);
  }

  function changePage(nextOffset: number) {
    if (!batchId) return;
    setOffset(nextOffset);
    setSelectedIds(new Set());
    void loadPage(batchId, nextOffset, tab, filters);
  }

  function togglePageSelection(checked: boolean) {
    const pageIds = preview?.rows.map((row) => row.id) ?? [];
    setSelectedIds((current) => {
      const next = new Set(current);
      for (const id of pageIds) {
        if (checked) next.add(id);
        else next.delete(id);
      }
      return next;
    });
  }

  function startOver() {
    onBatchIdChange(undefined);
    setUploadError(null);
    setActionNotice(null);
  }

  const summary = preview?.summary;
  const selectedRows = useMemo(
    () => filterSelectedRows(preview?.rows ?? [], selectedIds),
    [preview, selectedIds],
  );
  const tabCounts = summary ? {
    needs_review: summary.needs_review_count,
    duplicates: summary.duplicate_count,
    errors: summary.error_count,
    uncategorized: summary.uncategorized_count,
    ready: summary.auto_ready_count,
    excluded: summary.excluded_count,
    all: summary.total_rows,
  } : {
    needs_review: 0, duplicates: 0, errors: 0, uncategorized: 0, ready: 0, excluded: 0, all: 0,
  };

  return (
    <section className="import-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Family Cash Flow</p>
          <h1>{t.pageTitle}</h1>
          <p className="subtitle">{t.pageSubtitle}</p>
        </div>
        {batchId && preview?.summary.status === "draft" && (
          <button className="secondary-button" onClick={() => void loadPage(batchId, offset, tab, filters)} type="button">
            {t.refresh}
          </button>
        )}
      </header>

      {!batchId && <ImportUploader error={uploadError} busy={uploading} locale={locale} onUpload={handleUpload} />}
      {batchId && pageLoading && !preview && (
        <section className="empty-state"><h2>{t.loadingPreview}</h2></section>
      )}
      {batchId && pageError && !preview && <p className="table-error" role="alert">{pageError}</p>}
      {summary && (
        <>
          <ImportSummaryPanel locale={locale} summary={summary} />
          {summary.status === "confirmed" ? (
            <ImportConfirmed
              alreadyConfirmed={!confirmResult}
              locale={locale}
              onGoDashboard={onGoDashboard}
              onStartOver={startOver}
              result={confirmResult}
              summary={summary}
            />
          ) : (
            <>
              {pageError && <p className="table-error" role="alert">{pageError}</p>}
              {categoriesError && <p className="table-error" role="alert">{categoriesError}</p>}
              {accountsError && <p className="table-error" role="alert">{accountsError}</p>}
              {actionNotice && <p className="import-action-notice" role="status">{actionNotice}</p>}
              <ImportFilters
                categories={categories}
                filters={filters}
                locale={locale}
                matchingRowsCount={summary.matching_rows_count}
                onFiltersApply={applyFilters}
                onTabChange={changeTab}
                summaryCounts={tabCounts}
                tab={tab}
              />
              {pageLoading && <p className="field-help">{t.loadingPreview}</p>}
              <div className="import-selection-bar">
                <label className="import-check-row">
                  <input
                    checked={preview.rows.length > 0 && preview.rows.every((row) => selectedIds.has(row.id))}
                    disabled={preview.rows.length === 0 || bulkBusy}
                    onChange={(event) => togglePageSelection(event.target.checked)}
                    type="checkbox"
                  />
                  <span>{t.selectPage}</span>
                </label>
                <button className="text-button" disabled={selectedIds.size === 0 || bulkBusy} onClick={() => setSelectedIds(new Set())} type="button">
                  {t.clearSelection}
                </button>
                <span>{interpolate(t.selectedRows, { count: selectedIds.size })}</span>
              </div>
              <ImportPreviewTable
                locale={locale}
                onEdit={setEditingRow}
                onExclude={(row) => void excludeRow(row)}
                onToggleRow={(rowId) => setSelectedIds((current) => {
                  const next = new Set(current);
                  if (next.has(rowId)) next.delete(rowId);
                  else next.add(rowId);
                  return next;
                })}
                rows={preview.rows}
                savingRowId={savingRowId}
                selectedIds={selectedIds}
              />
              <div className="import-pagination">
                <span>{pageRange(summary.offset, summary.returned_rows, summary.matching_rows_count, t.showing, t.of)}</span>
                <div>
                  <button className="secondary-button" disabled={summary.offset <= 0 || pageLoading} onClick={() => changePage(Math.max(0, summary.offset - summary.limit))} type="button">{t.previous}</button>
                  <button className="secondary-button" disabled={summary.offset + summary.returned_rows >= summary.matching_rows_count || pageLoading} onClick={() => changePage(summary.offset + summary.limit)} type="button">{t.next}</button>
                </div>
              </div>
              <BulkActions
                busy={bulkBusy}
                categories={categories}
                locale={locale}
                onApply={applyBulkAction}
                selectedRows={selectedRows}
              />
              {categories.length === 0 && !categoriesError && <p className="field-help">{t.categoryLoadError}</p>}
              <ImportConfirmation
                accounts={accounts}
                accountsLoading={accountsLoading}
                duplicateSkippedCount={duplicateSkippedCount}
                error={confirmError}
                confirming={confirming}
                locale={locale}
                onAccountChange={setSelectedAccountId}
                onConfirm={() => void handleConfirm()}
                selectedAccountId={selectedAccountId}
                summary={summary}
              />
              <ImportRowEditor
                categories={categories}
                locale={locale}
                onClose={() => setEditingRow(null)}
                onSave={(payload) => void handleRowSave(payload)}
                row={editingRow}
                saving={savingRowId === editingRow?.id}
              />
            </>
          )}
        </>
      )}
      {batchId && pageError && preview && <p className="table-error" role="alert">{pageError}</p>}
    </section>
  );
}

function apiFilters(
  tab: ImportTab,
  extra: AppliedImportFilters,
  offset: number,
): ImportPreviewFilters {
  const filters: ImportPreviewFilters = { offset, limit: PAGE_SIZE, ...extra };
  if (tab === "needs_review") filters.row_status = "needs_review";
  if (tab === "duplicates") filters.row_status = "duplicate_candidate";
  if (tab === "errors") filters.row_status = "error";
  if (tab === "ready") filters.row_status = "auto_ready";
  if (tab === "excluded") filters.row_status = "excluded";
  if (tab === "uncategorized") filters.uncategorized_only = true;
  return filters;
}

function pageRange(offset: number, returned: number, total: number, showing: string, of: string) {
  if (total === 0 || returned === 0) return `${showing}: 0 ${of} ${total}`;
  return `${showing}: ${offset + 1}–${offset + returned} ${of} ${total}`;
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}
