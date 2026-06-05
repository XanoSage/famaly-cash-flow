import {
  Activity,
  AlertCircle,
  CalendarDays,
  Filter,
  PiggyBank,
  RefreshCw,
  Store,
  Tags,
  TrendingUp,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Locale = "ru" | "uk";
type ScopeFilter = "all" | "family" | "work_fop";

type Summary = {
  income: string;
  expenses: string;
  savings: string;
  transfers: string;
  net_cash_flow: string;
  average_daily_expense: string;
  transaction_count: number;
  expense_count: number;
  income_count: number;
  savings_count: number;
  transfer_count: number;
  needs_review_count: number;
  uncategorized_count: number;
  work_fop_count: number;
};

type TimelineRow = {
  period: string;
  income: string;
  expenses: string;
  savings: string;
  transfers: string;
  net_cash_flow: string;
};

type Timeline = {
  granularity: string;
  rows: TimelineRow[];
};

type CategoryRow = {
  category_id: string | null;
  category_name: string;
  amount: string;
  transaction_count: number;
  share_percent: string;
};

type CategoryAnalytics = {
  total_amount: string;
  total_transactions: number;
  rows: CategoryRow[];
};

type MerchantRow = {
  merchant_id: string;
  merchant_name: string;
  merchant_type: string;
  amount: string;
  transaction_count: number;
  share_percent: string;
};

type MerchantAnalytics = {
  total_amount: string;
  total_transactions: number;
  rows: MerchantRow[];
};

type InsightRow = {
  code: string;
  title: string;
  message: string;
  severity: "info" | "warning" | "positive";
};

type Dashboard = {
  summary: Summary;
  timeline: Timeline;
  top_categories: CategoryAnalytics;
  top_merchants: MerchantAnalytics;
  insights: {
    rows: InsightRow[];
  };
};

type LoadState =
  | { status: "idle"; data: null; error: null }
  | { status: "loading"; data: Dashboard | null; error: null }
  | { status: "success"; data: Dashboard; error: null }
  | { status: "error"; data: Dashboard | null; error: string };

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

const copy = {
  ru: {
    title: "Семейный финансовый dashboard",
    subtitle: "Первый рабочий экран с реальными backend endpoints.",
    familyId: "Family ID",
    from: "С даты",
    to: "По дату",
    scope: "Слой",
    allScopes: "Все",
    familyScope: "Семья",
    workScope: "ФОП",
    refresh: "Обновить",
    loading: "Загружаю аналитику...",
    emptyTitle: "Введите Family ID",
    emptyText: "После импорта выписки сюда можно вставить id семьи и увидеть dashboard.",
    errorTitle: "Не удалось загрузить dashboard",
    apiHint: "Проверь, что backend запущен и VITE_API_BASE_URL указывает на API.",
    income: "Доходы",
    expenses: "Расходы",
    savings: "Накопления",
    cashFlow: "Cash flow",
    timeline: "Динамика",
    insights: "Подсказки",
    categories: "Категории",
    merchants: "Места покупок",
    transactions: "операций",
    uncategorized: "без категории",
    needsReview: "на проверку",
    noRows: "Нет данных за выбранный период",
    language: "Язык",
  },
  uk: {
    title: "Сімейний фінансовий dashboard",
    subtitle: "Перший робочий екран з реальними backend endpoints.",
    familyId: "Family ID",
    from: "З дати",
    to: "До дати",
    scope: "Шар",
    allScopes: "Усі",
    familyScope: "Сім'я",
    workScope: "ФОП",
    refresh: "Оновити",
    loading: "Завантажую аналітику...",
    emptyTitle: "Введіть Family ID",
    emptyText: "Після імпорту виписки сюди можна вставити id сім'ї та побачити dashboard.",
    errorTitle: "Не вдалося завантажити dashboard",
    apiHint: "Перевір, що backend запущений і VITE_API_BASE_URL вказує на API.",
    income: "Доходи",
    expenses: "Витрати",
    savings: "Накопичення",
    cashFlow: "Cash flow",
    timeline: "Динаміка",
    insights: "Підказки",
    categories: "Категорії",
    merchants: "Місця покупок",
    transactions: "операцій",
    uncategorized: "без категорії",
    needsReview: "на перевірку",
    noRows: "Немає даних за вибраний період",
    language: "Мова",
  },
} satisfies Record<Locale, Record<string, string>>;

export function App() {
  const [locale, setLocale] = useState<Locale>(() => readStoredValue("locale", "ru") as Locale);
  const [familyId, setFamilyId] = useState(() => readStoredValue("familyId", ""));
  const [occurredFrom, setOccurredFrom] = useState("");
  const [occurredTo, setOccurredTo] = useState("");
  const [scope, setScope] = useState<ScopeFilter>("family");
  const [state, setState] = useState<LoadState>({ status: "idle", data: null, error: null });

  const t = copy[locale];
  const formatter = useMemo(
    () =>
      new Intl.NumberFormat(locale === "uk" ? "uk-UA" : "ru-UA", {
        style: "currency",
        currency: "UAH",
        maximumFractionDigits: 2,
      }),
    [locale],
  );

  useEffect(() => {
    localStorage.setItem("familyId", familyId);
  }, [familyId]);

  useEffect(() => {
    localStorage.setItem("locale", locale);
  }, [locale]);

  async function loadDashboard() {
    if (!familyId.trim()) {
      setState({ status: "idle", data: null, error: null });
      return;
    }

    setState((current) => ({ status: "loading", data: current.data, error: null }));
    try {
      const url = new URL(`${API_BASE_URL}/analytics/dashboard`);
      url.searchParams.set("family_id", familyId.trim());
      if (occurredFrom) {
        url.searchParams.set("occurred_from", `${occurredFrom}T00:00:00`);
      }
      if (occurredTo) {
        url.searchParams.set("occurred_to", `${occurredTo}T23:59:59`);
      }
      if (scope !== "all") {
        url.searchParams.set("scope", scope);
      }

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      const data = (await response.json()) as Dashboard;
      setState({ status: "success", data, error: null });
    } catch (error) {
      setState((current) => ({
        status: "error",
        data: current.data,
        error: error instanceof Error ? error.message : "Unknown error",
      }));
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadDashboard();
  }

  const dashboard = state.data;
  const chartRows = useMemo(() => toChartRows(dashboard?.timeline.rows ?? []), [dashboard]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Family Cash Flow</p>
          <h1>{t.title}</h1>
          <p className="subtitle">{t.subtitle}</p>
        </div>
        <label className="language-control">
          <span>{t.language}</span>
          <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
            <option value="ru">RU</option>
            <option value="uk">UA</option>
          </select>
        </label>
      </header>

      <form className="filters" onSubmit={handleSubmit}>
        <label className="field field-wide">
          <span>{t.familyId}</span>
          <input
            value={familyId}
            onChange={(event) => setFamilyId(event.target.value)}
            placeholder="00000000-0000-0000-0000-000000000000"
          />
        </label>
        <label className="field">
          <span>{t.from}</span>
          <input
            type="date"
            value={occurredFrom}
            onChange={(event) => setOccurredFrom(event.target.value)}
          />
        </label>
        <label className="field">
          <span>{t.to}</span>
          <input
            type="date"
            value={occurredTo}
            onChange={(event) => setOccurredTo(event.target.value)}
          />
        </label>
        <label className="field">
          <span>{t.scope}</span>
          <select value={scope} onChange={(event) => setScope(event.target.value as ScopeFilter)}>
            <option value="family">{t.familyScope}</option>
            <option value="work_fop">{t.workScope}</option>
            <option value="all">{t.allScopes}</option>
          </select>
        </label>
        <button className="primary-button" type="submit" disabled={state.status === "loading"}>
          {state.status === "loading" ? <RefreshCw className="spin" /> : <Filter />}
          <span>{t.refresh}</span>
        </button>
      </form>

      {state.status === "idle" && (
        <section className="empty-state">
          <Wallet />
          <h2>{t.emptyTitle}</h2>
          <p>{t.emptyText}</p>
        </section>
      )}

      {state.status === "error" && (
        <section className="notice notice-warning">
          <AlertCircle />
          <div>
            <h2>{t.errorTitle}</h2>
            <p>{state.error}</p>
            <p>{t.apiHint}</p>
          </div>
        </section>
      )}

      {state.status === "loading" && !dashboard && (
        <section className="empty-state">
          <RefreshCw className="spin" />
          <h2>{t.loading}</h2>
        </section>
      )}

      {dashboard && (
        <>
          <section className="kpi-grid">
            <KpiCard icon={TrendingUp} label={t.income} value={money(dashboard.summary.income, formatter)} />
            <KpiCard icon={Wallet} label={t.expenses} value={money(dashboard.summary.expenses, formatter)} />
            <KpiCard icon={PiggyBank} label={t.savings} value={money(dashboard.summary.savings, formatter)} />
            <KpiCard
              icon={Activity}
              label={t.cashFlow}
              value={money(dashboard.summary.net_cash_flow, formatter)}
              tone={Number(dashboard.summary.net_cash_flow) < 0 ? "warning" : "positive"}
            />
          </section>

          <section className="metric-strip">
            <SmallMetric label={t.transactions} value={dashboard.summary.transaction_count} />
            <SmallMetric label={t.uncategorized} value={dashboard.summary.uncategorized_count} />
            <SmallMetric label={t.needsReview} value={dashboard.summary.needs_review_count} />
          </section>

          <section className="dashboard-grid">
            <section className="panel panel-wide">
              <PanelTitle icon={CalendarDays} title={t.timeline} />
              {chartRows.length > 0 ? (
                <div className="chart-frame">
                  <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={chartRows}>
                      <defs>
                        <linearGradient id="expensesFill" x1="0" x2="0" y1="0" y2="1">
                          <stop offset="5%" stopColor="#d84c43" stopOpacity={0.24} />
                          <stop offset="95%" stopColor="#d84c43" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="incomeFill" x1="0" x2="0" y1="0" y2="1">
                          <stop offset="5%" stopColor="#2d8f6f" stopOpacity={0.22} />
                          <stop offset="95%" stopColor="#2d8f6f" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="#e5ebf3" vertical={false} />
                      <XAxis dataKey="period" tickLine={false} axisLine={false} />
                      <YAxis tickLine={false} axisLine={false} width={76} />
                      <Tooltip formatter={(value) => money(String(value), formatter)} />
                      <Area
                        type="monotone"
                        dataKey="income"
                        stroke="#2d8f6f"
                        fill="url(#incomeFill)"
                        strokeWidth={2}
                      />
                      <Area
                        type="monotone"
                        dataKey="expenses"
                        stroke="#d84c43"
                        fill="url(#expensesFill)"
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyRows text={t.noRows} />
              )}
            </section>

            <section className="panel">
              <PanelTitle icon={AlertCircle} title={t.insights} />
              <div className="insight-list">
                {dashboard.insights.rows.length > 0 ? (
                  dashboard.insights.rows.map((insight) => (
                    <article className={`insight insight-${insight.severity}`} key={insight.code}>
                      <strong>{insight.title}</strong>
                      <p>{insight.message}</p>
                    </article>
                  ))
                ) : (
                  <EmptyRows text={t.noRows} />
                )}
              </div>
            </section>

            <section className="panel">
              <PanelTitle icon={Tags} title={t.categories} />
              <RankedList
                emptyText={t.noRows}
                formatter={formatter}
                rows={dashboard.top_categories.rows.map((row) => ({
                  id: row.category_id ?? row.category_name,
                  name: row.category_name,
                  amount: row.amount,
                  count: row.transaction_count,
                  share: row.share_percent,
                }))}
              />
            </section>

            <section className="panel">
              <PanelTitle icon={Store} title={t.merchants} />
              <RankedList
                emptyText={t.noRows}
                formatter={formatter}
                rows={dashboard.top_merchants.rows.map((row) => ({
                  id: row.merchant_id,
                  name: row.merchant_name,
                  amount: row.amount,
                  count: row.transaction_count,
                  share: row.share_percent,
                }))}
              />
            </section>
          </section>
        </>
      )}
    </main>
  );
}

function KpiCard({
  icon: Icon,
  label,
  value,
  tone = "neutral",
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone?: "neutral" | "positive" | "warning";
}) {
  return (
    <article className={`kpi-card kpi-${tone}`}>
      <Icon />
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function SmallMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="small-metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function PanelTitle({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="panel-title">
      <Icon />
      <h2>{title}</h2>
    </div>
  );
}

function RankedList({
  rows,
  formatter,
  emptyText,
}: {
  rows: Array<{ id: string; name: string; amount: string; count: number; share: string }>;
  formatter: Intl.NumberFormat;
  emptyText: string;
}) {
  if (rows.length === 0) {
    return <EmptyRows text={emptyText} />;
  }

  return (
    <div className="ranked-list">
      {rows.map((row) => (
        <article className="ranked-row" key={row.id}>
          <div>
            <strong>{row.name}</strong>
            <span>
              {row.count} / {row.share}%
            </span>
          </div>
          <b>{money(row.amount, formatter)}</b>
        </article>
      ))}
    </div>
  );
}

function EmptyRows({ text }: { text: string }) {
  return <p className="empty-rows">{text}</p>;
}

function money(value: string, formatter: Intl.NumberFormat) {
  return formatter.format(Number(value));
}

function toChartRows(rows: TimelineRow[]) {
  return rows.map((row) => ({
    period: row.period.slice(5),
    income: Number(row.income),
    expenses: Number(row.expenses),
    savings: Number(row.savings),
  }));
}

function readStoredValue(key: string, fallback: string) {
  if (typeof localStorage === "undefined") {
    return fallback;
  }
  return localStorage.getItem(key) ?? fallback;
}
