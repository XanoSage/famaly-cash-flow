import {
  Activity,
  AlertCircle,
  CalendarDays,
  CheckCircle,
  Filter,
  PiggyBank,
  RefreshCw,
  ReceiptText,
  Store,
  Tags,
  TrendingUp,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
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

type TransactionRow = {
  id: string;
  occurred_at: string;
  amount: string;
  currency: string;
  direction: string;
  flow_type: string;
  scope: string;
  description_raw: string | null;
  merchant_name: string | null;
  category_id: string | null;
  category_name: string | null;
  needs_review: boolean;
};

type TransactionList = {
  total: number;
  offset: number;
  limit: number;
  rows: TransactionRow[];
};

type LoadState =
  | { status: "idle"; data: null; error: null }
  | { status: "loading"; data: Dashboard | null; error: null }
  | { status: "success"; data: Dashboard; error: null }
  | { status: "error"; data: Dashboard | null; error: string };

type TransactionsState =
  | { status: "idle"; data: null; error: null }
  | { status: "loading"; data: TransactionList | null; error: null }
  | { status: "success"; data: TransactionList; error: null }
  | { status: "error"; data: TransactionList | null; error: string };

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

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
    savedFamilyIdHint: "Family ID сохраняется в этом браузере и загрузится автоматически при следующем открытии.",
    errorTitle: "Не удалось загрузить dashboard",
    apiHint: "Проверь, что backend запущен и VITE_API_BASE_URL указывает на API.",
    invalidFamilyId: "Family ID должен быть UUID в формате 00000000-0000-0000-0000-000000000000.",
    networkError: "Не удалось достучаться до backend. Проверь, что FastAPI запущен на 8000 порту.",
    notFoundError: "Для этого Family ID данные не найдены. Проверь id или заново запусти demo seed.",
    serverError: "Backend ответил ошибкой. Проверь, что PostgreSQL запущен и миграции применены.",
    unknownError: "Неизвестная ошибка загрузки dashboard.",
    income: "Доходы",
    expenses: "Расходы",
    savings: "Накопления",
    cashFlow: "Cash flow",
    timeline: "Динамика",
    insights: "Подсказки",
    categories: "Категории",
    merchants: "Места покупок",
    recentTransactions: "Последние операции",
    reviewOnly: "Только на проверку",
    reviewBadge: "на проверку",
    markReviewed: "Готово",
    updating: "Сохраняю...",
    reviewQueueEmpty: "Нет операций, которые требуют проверки",
    noCategory: "без категории",
    transactionDate: "Дата",
    transactionDetails: "Описание",
    transactionScope: "Слой",
    transactionAmount: "Сумма",
    transactionsShowing: "Показано",
    transactionsOf: "из",
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
    savedFamilyIdHint: "Family ID зберігається у цьому браузері та завантажиться автоматично при наступному відкритті.",
    errorTitle: "Не вдалося завантажити dashboard",
    apiHint: "Перевір, що backend запущений і VITE_API_BASE_URL вказує на API.",
    invalidFamilyId: "Family ID має бути UUID у форматі 00000000-0000-0000-0000-000000000000.",
    networkError: "Не вдалося підключитися до backend. Перевір, що FastAPI запущений на 8000 порту.",
    notFoundError: "Для цього Family ID дані не знайдені. Перевір id або заново запусти demo seed.",
    serverError: "Backend відповів помилкою. Перевір, що PostgreSQL запущений і міграції застосовані.",
    unknownError: "Невідома помилка завантаження dashboard.",
    income: "Доходи",
    expenses: "Витрати",
    savings: "Накопичення",
    cashFlow: "Cash flow",
    timeline: "Динаміка",
    insights: "Підказки",
    categories: "Категорії",
    merchants: "Місця покупок",
    recentTransactions: "Останні операції",
    reviewOnly: "Тільки на перевірку",
    reviewBadge: "на перевірку",
    markReviewed: "Готово",
    updating: "Зберігаю...",
    reviewQueueEmpty: "Немає операцій, які потребують перевірки",
    noCategory: "без категорії",
    transactionDate: "Дата",
    transactionDetails: "Опис",
    transactionScope: "Шар",
    transactionAmount: "Сума",
    transactionsShowing: "Показано",
    transactionsOf: "з",
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
  const [reviewOnly, setReviewOnly] = useState(false);
  const [state, setState] = useState<LoadState>({ status: "idle", data: null, error: null });
  const [transactionsState, setTransactionsState] = useState<TransactionsState>({
    status: "idle",
    data: null,
    error: null,
  });
  const [updatingTransactionId, setUpdatingTransactionId] = useState<string | null>(null);
  const hasAutoLoadedRef = useRef(false);

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

  useEffect(() => {
    if (!hasAutoLoadedRef.current && familyId.trim()) {
      hasAutoLoadedRef.current = true;
      void loadDashboard();
    }
  }, []);

  useEffect(() => {
    const normalizedFamilyId = familyId.trim();
    if (state.data && UUID_PATTERN.test(normalizedFamilyId)) {
      void loadTransactions(normalizedFamilyId, reviewOnly);
    }
  }, [reviewOnly]);

  async function loadDashboard() {
    const normalizedFamilyId = familyId.trim();
    if (!normalizedFamilyId) {
      setState({ status: "idle", data: null, error: null });
      setTransactionsState({ status: "idle", data: null, error: null });
      return;
    }
    if (!UUID_PATTERN.test(normalizedFamilyId)) {
      setState((current) => ({
        status: "error",
        data: current.data,
        error: t.invalidFamilyId,
      }));
      setTransactionsState((current) => ({
        status: "error",
        data: current.data,
        error: t.invalidFamilyId,
      }));
      return;
    }

    setState((current) => ({ status: "loading", data: current.data, error: null }));
    setTransactionsState((current) => ({ status: "loading", data: current.data, error: null }));
    try {
      const url = buildFilteredUrl(`${API_BASE_URL}/analytics/dashboard`, normalizedFamilyId, {
        occurredFrom,
        occurredTo,
        scope,
      });

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(dashboardErrorMessage(response.status, t));
      }
      const data = (await response.json()) as Dashboard;
      setState({ status: "success", data, error: null });
    } catch (error) {
      setState((current) => ({
        status: "error",
        data: current.data,
        error: error instanceof TypeError ? t.networkError : errorMessage(error, t.unknownError),
      }));
    }

    await loadTransactions(normalizedFamilyId, reviewOnly);
  }

  async function loadTransactions(normalizedFamilyId: string, onlyReview: boolean) {
    setTransactionsState((current) => ({ status: "loading", data: current.data, error: null }));
    try {
      const url = buildFilteredUrl(`${API_BASE_URL}/transactions`, normalizedFamilyId, {
        occurredFrom,
        occurredTo,
        scope,
      });
      url.searchParams.set("limit", "20");
      if (onlyReview) {
        url.searchParams.set("needs_review", "true");
      }

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(dashboardErrorMessage(response.status, t));
      }
      const data = (await response.json()) as TransactionList;
      setTransactionsState({ status: "success", data, error: null });
    } catch (error) {
      setTransactionsState((current) => ({
        status: "error",
        data: current.data,
        error: error instanceof TypeError ? t.networkError : errorMessage(error, t.unknownError),
      }));
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadDashboard();
  }

  async function markTransactionReviewed(transactionId: string) {
    const normalizedFamilyId = familyId.trim();
    if (!UUID_PATTERN.test(normalizedFamilyId)) {
      setTransactionsState((current) => ({
        status: "error",
        data: current.data,
        error: t.invalidFamilyId,
      }));
      return;
    }

    setUpdatingTransactionId(transactionId);
    try {
      const url = new URL(`${API_BASE_URL}/transactions/${transactionId}`);
      url.searchParams.set("family_id", normalizedFamilyId);
      const response = await fetch(url, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ needs_review: false }),
      });
      if (!response.ok) {
        throw new Error(dashboardErrorMessage(response.status, t));
      }
      await loadDashboard();
    } catch (error) {
      setTransactionsState((current) => ({
        status: "error",
        data: current.data,
        error: error instanceof TypeError ? t.networkError : errorMessage(error, t.unknownError),
      }));
    } finally {
      setUpdatingTransactionId(null);
    }
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
          <small>{t.savedFamilyIdHint}</small>
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

          <section className="panel">
            <div className="panel-heading">
              <PanelTitle icon={ReceiptText} title={t.recentTransactions} />
              <label className="toggle-control">
                <input
                  checked={reviewOnly}
                  onChange={(event) => setReviewOnly(event.target.checked)}
                  type="checkbox"
                />
                <span>{t.reviewOnly}</span>
              </label>
            </div>
            {transactionsState.status === "error" && (
              <p className="table-error">{transactionsState.error}</p>
            )}
            {transactionsState.status === "loading" && !transactionsState.data ? (
              <EmptyRows text={t.loading} />
            ) : (
              <TransactionsTable
                emptyText={reviewOnly ? t.reviewQueueEmpty : t.noRows}
                formatter={formatter}
                onMarkReviewed={markTransactionReviewed}
                rows={transactionsState.data?.rows ?? []}
                t={t}
                total={transactionsState.data?.total ?? 0}
                updatingTransactionId={updatingTransactionId}
              />
            )}
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

function TransactionsTable({
  rows,
  total,
  formatter,
  emptyText,
  onMarkReviewed,
  t,
  updatingTransactionId,
}: {
  rows: TransactionRow[];
  total: number;
  formatter: Intl.NumberFormat;
  emptyText: string;
  onMarkReviewed: (transactionId: string) => void;
  t: Record<string, string>;
  updatingTransactionId: string | null;
}) {
  if (rows.length === 0) {
    return <EmptyRows text={emptyText} />;
  }

  return (
    <div className="transactions-block">
      <p className="table-summary">
        {t.transactionsShowing} {rows.length} {t.transactionsOf} {total}
      </p>
      <div className="transactions-table">
        <div className="transactions-head">
          <span>{t.transactionDate}</span>
          <span>{t.transactionDetails}</span>
          <span>{t.transactionScope}</span>
          <span>{t.transactionAmount}</span>
          <span />
        </div>
        {rows.map((row) => (
          <article className={`transaction-row ${row.needs_review ? "transaction-review" : ""}`} key={row.id}>
            <time dateTime={row.occurred_at}>{formatDate(row.occurred_at)}</time>
            <div className="transaction-main">
              <strong>{row.merchant_name ?? row.description_raw ?? row.flow_type}</strong>
              <span>
                {row.flow_type} / {row.category_name ?? t.noCategory}
              </span>
              {row.needs_review && <em>{t.reviewBadge}</em>}
            </div>
            <span className="scope-pill">{row.scope}</span>
            <b className={Number(row.amount) < 0 ? "amount-negative" : "amount-positive"}>
              {money(row.amount, formatter)}
            </b>
            <div className="transaction-actions">
              {row.needs_review && (
                <button
                  className="review-button"
                  disabled={updatingTransactionId === row.id}
                  onClick={() => onMarkReviewed(row.id)}
                  type="button"
                >
                  {updatingTransactionId === row.id ? <RefreshCw className="spin" /> : <CheckCircle />}
                  <span>{updatingTransactionId === row.id ? t.updating : t.markReviewed}</span>
                </button>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function money(value: string, formatter: Intl.NumberFormat) {
  return formatter.format(Number(value));
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("uk-UA", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function toChartRows(rows: TimelineRow[]) {
  return rows.map((row) => ({
    period: row.period.slice(5),
    income: Number(row.income),
    expenses: Number(row.expenses),
    savings: Number(row.savings),
  }));
}

function buildFilteredUrl(
  href: string,
  familyId: string,
  filters: { occurredFrom: string; occurredTo: string; scope: ScopeFilter },
) {
  const url = new URL(href);
  url.searchParams.set("family_id", familyId);
  if (filters.occurredFrom) {
    url.searchParams.set("occurred_from", `${filters.occurredFrom}T00:00:00`);
  }
  if (filters.occurredTo) {
    url.searchParams.set("occurred_to", `${filters.occurredTo}T23:59:59`);
  }
  if (filters.scope !== "all") {
    url.searchParams.set("scope", filters.scope);
  }
  return url;
}

function dashboardErrorMessage(status: number, t: Record<string, string>) {
  if (status === 404) {
    return t.notFoundError;
  }
  if (status >= 500) {
    return t.serverError;
  }
  return `${status}: ${t.unknownError}`;
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function readStoredValue(key: string, fallback: string) {
  if (typeof localStorage === "undefined") {
    return fallback;
  }
  return localStorage.getItem(key) ?? fallback;
}
