import type {
  Account,
  ConfirmImportResponse,
  ImportSummary,
} from "../api";
import { importCopy } from "./importCopy";
import type { Locale } from "./types";

export function ImportConfirmation({
  locale,
  summary,
  duplicateSkippedCount,
  accounts,
  accountsLoading,
  selectedAccountId,
  confirming,
  error,
  onAccountChange,
  onConfirm,
}: {
  locale: Locale;
  summary: ImportSummary;
  duplicateSkippedCount: number;
  accounts: Account[];
  accountsLoading: boolean;
  selectedAccountId: string;
  confirming: boolean;
  error: string | null;
  onAccountChange: (accountId: string) => void;
  onConfirm: () => void;
}) {
  const t = importCopy[locale];
  const hasErrors = summary.error_count > 0;
  return (
    <section className="panel import-confirm-panel">
      <div>
        <p className="eyebrow">{t.confirmTitle}</p>
        <h2>{t.confirmTitle}</h2>
      </div>
      <div className="confirm-metrics">
        <Metric label={t.expectedImported} value={summary.imported_count} />
        <Metric label={t.excluded} value={summary.excluded_count} />
        <Metric label={t.duplicatesWillSkip} value={duplicateSkippedCount} />
        <Metric label={t.uncategorized} value={summary.uncategorized_count} />
        <Metric label={t.work} value={summary.work_fop_count} />
      </div>
      {duplicateSkippedCount > 0 && <p className="field-help">{t.duplicateNote}</p>}
      {summary.uncategorized_count > 0 && <p className="field-help">{t.confirmWarning}</p>}
      {hasErrors && <p className="table-error" role="alert">{t.errorsBlockConfirm} ({summary.error_count})</p>}
      <label className="field import-account-select">
        <span>{t.account}</span>
        <select
          disabled={accountsLoading || confirming || accounts.length === 0}
          value={selectedAccountId}
          onChange={(event) => onAccountChange(event.target.value)}
        >
          <option value="">{accountsLoading ? t.accountsLoading : t.chooseAccount}</option>
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>{account.name} — {account.currency}</option>
          ))}
        </select>
      </label>
      {accounts.length === 0 && !accountsLoading && <p className="table-error">{t.noAccounts}</p>}
      {error && <p className="table-error" role="alert">{error}</p>}
      <button
        className="primary-button confirm-import-button"
        disabled={hasErrors || !selectedAccountId || confirming || accountsLoading || accounts.length === 0}
        onClick={onConfirm}
        type="button"
      >
        {confirming ? t.confirming : t.confirm}
      </button>
    </section>
  );
}

export function ImportConfirmed({
  locale,
  summary,
  result,
  alreadyConfirmed = false,
  onGoDashboard,
  onStartOver,
}: {
  locale: Locale;
  summary: ImportSummary;
  result: ConfirmImportResponse | null;
  alreadyConfirmed?: boolean;
  onGoDashboard: () => void;
  onStartOver: () => void;
}) {
  const t = importCopy[locale];
  const created = result?.created_transactions ?? summary.imported_count;
  const excluded = result?.excluded_count ?? summary.excluded_count;
  const duplicates = result?.duplicate_count ?? summary.duplicate_count;
  const uncategorized = result?.uncategorized_count ?? summary.uncategorized_count;
  const work = result?.work_fop_count ?? summary.work_fop_count;

  return (
    <section className="panel import-confirmed-panel" role="status">
      <div className="import-success-mark" aria-hidden="true">✓</div>
      <p className="eyebrow">{t.pageTitle}</p>
      <h2>{alreadyConfirmed ? t.alreadyConfirmedTitle : t.resultTitle}</h2>
      <div className="confirm-metrics">
        <Metric label={t.created} value={created} />
        <Metric label={t.resultExcluded} value={excluded} />
        <Metric label={t.resultDuplicates} value={duplicates} />
        <Metric label={t.resultUncategorized} value={uncategorized} />
        <Metric label={t.resultWork} value={work} />
      </div>
      <div className="import-confirmed-actions">
        <button className="primary-button" onClick={onGoDashboard} type="button">{t.goDashboard}</button>
        <button className="secondary-button" onClick={onStartOver} type="button">{t.startOver}</button>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div className="confirm-metric"><strong>{value}</strong><span>{label}</span></div>;
}
