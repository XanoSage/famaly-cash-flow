import type { ImportSummary as ImportSummaryData } from "../api";
import { importCopy } from "./importCopy";
import type { Locale } from "./types";

export function ImportSummary({ summary, locale }: { summary: ImportSummaryData; locale: Locale }) {
  const t = importCopy[locale];
  const period = summary.period_start && summary.period_end
    ? `${formatDate(summary.period_start, locale)} – ${formatDate(summary.period_end, locale)}`
    : t.emptyPeriod;
  const metrics = [
    { label: t.totals, value: summary.total_rows, tone: "" },
    { label: t.ready, value: summary.auto_ready_count, tone: "" },
    { label: t.needsReview, value: summary.needs_review_count, tone: "attention" },
    { label: t.duplicates, value: summary.duplicate_count, tone: "attention" },
    { label: t.errors, value: summary.error_count, tone: "danger" },
    { label: t.excluded, value: summary.excluded_count, tone: "" },
    { label: t.uncategorized, value: summary.uncategorized_count, tone: "" },
    { label: t.work, value: summary.work_fop_count, tone: "" },
    { label: t.savings, value: summary.savings_count, tone: "" },
  ];

  return (
    <section className="panel import-summary" aria-label={t.reviewTitle}>
      <div className="import-summary-heading">
        <div>
          <p className="eyebrow">{t.fileLabel}</p>
          <h2>{summary.source_filename}</h2>
        </div>
        <p className="import-period"><strong>{t.period}:</strong> {period}</p>
      </div>
      <div className="import-metrics">
        {metrics.map((metric) => (
          <div className={`import-metric ${metric.tone}`} key={metric.label}>
            <strong>{metric.value}</strong>
            <span>{metric.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function formatDate(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "uk" ? "uk-UA" : "ru-UA", {
    dateStyle: "medium",
  }).format(new Date(value));
}
