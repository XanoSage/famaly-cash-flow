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
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  apiUrl,
  authenticatedFetch,
  clearAccessToken,
  createTelegramLink,
  deleteTelegramLink,
  getCategories,
  getTelegramLinkStatus,
  getCurrentUser,
  refreshAccessToken,
  signIn,
  signOut,
  type CurrentUser,
  type TelegramLinkStatus,
  type TelegramLinkToken,
} from "./api";
import { ImportPage } from "./import/ImportPage";
import { TransactionsPage } from "./transactions/TransactionsPage";
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
type AppPage = "dashboard" | "transactions" | "import" | "account";
type AppRoute = { page: AppPage; batchId?: string };

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

type CategoryOption = {
  id: string;
  name: string;
  is_system: boolean;
};

type CategoryList = {
  rows: CategoryOption[];
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

const copy = {
  ru: {
    title: "Семейный финансовый dashboard",
    subtitle: "Первый рабочий экран с реальными backend endpoints.",
    navDashboard: "Дашборд",
    navImport: "Импорт",
    navTransactions: "Операции",
    navAccount: "Аккаунт / Telegram",
    signIn: "Войти",
    signOut: "Выйти",
    email: "Email",
    password: "Пароль",
    loginTitle: "Вход в Family Cash Flow",
    loginHelp: "Введите email и пароль пользователя вашей семьи.",
    loginError: "Не удалось войти. Проверьте email и пароль.",
    account: "Семья",
    from: "С даты",
    to: "По дату",
    scope: "Слой",
    allScopes: "Все",
    familyScope: "Семья",
    workScope: "ФОП",
    refresh: "Обновить",
    loading: "Загружаю аналитику...",
    emptyTitle: "Пока нет данных",
    emptyText: "После импорта выписки здесь появится семейная аналитика.",
    errorTitle: "Не удалось загрузить dashboard",
    apiHint: "Проверь, что backend запущен и VITE_API_BASE_URL указывает на API.",
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
    chooseCategory: "Выбрать категорию",
    categoryLoadError: "Не удалось загрузить категории.",
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
    telegramTitle: "Telegram",
    telegramLinked: "Telegram связан",
    telegramNotLinked: "Telegram не связан",
    telegramLinkedAs: "Аккаунт Telegram",
    telegramGenerate: "Создать ссылку",
    telegramRegenerate: "Создать новую ссылку",
    telegramUnlink: "Отвязать Telegram",
    telegramOpen: "Открыть Telegram",
    telegramCopy: "Скопировать ссылку",
    telegramCopyToken: "Скопировать токен",
    telegramCopied: "Скопировано",
    telegramExpires: "Ссылка действительна до",
    telegramManualStart: "Откройте своего бота и отправьте команду /start с этим токеном:",
    telegramRefresh: "Обновить статус",
    telegramLoadError: "Не удалось загрузить статус Telegram.",
    telegramActionError: "Не удалось выполнить действие с Telegram.",
    telegramUnlinkConfirm: "Отвязать Telegram от вашего аккаунта?",
  },
  uk: {
    title: "Сімейний фінансовий dashboard",
    subtitle: "Перший робочий екран з реальними backend endpoints.",
    navDashboard: "Дашборд",
    navImport: "Імпорт",
    navTransactions: "Операції",
    navAccount: "Обліковий запис / Telegram",
    signIn: "Увійти",
    signOut: "Вийти",
    email: "Email",
    password: "Пароль",
    loginTitle: "Вхід у Family Cash Flow",
    loginHelp: "Введіть email і пароль користувача вашої родини.",
    loginError: "Не вдалося увійти. Перевірте email і пароль.",
    account: "Родина",
    from: "З дати",
    to: "До дати",
    scope: "Шар",
    allScopes: "Усі",
    familyScope: "Сім'я",
    workScope: "ФОП",
    refresh: "Оновити",
    loading: "Завантажую аналітику...",
    emptyTitle: "Поки немає даних",
    emptyText: "Після імпорту виписки тут з'явиться сімейна аналітика.",
    errorTitle: "Не вдалося завантажити dashboard",
    apiHint: "Перевір, що backend запущений і VITE_API_BASE_URL вказує на API.",
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
    chooseCategory: "Вибрати категорію",
    categoryLoadError: "Не вдалося завантажити категорії.",
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
    telegramTitle: "Telegram",
    telegramLinked: "Telegram підключено",
    telegramNotLinked: "Telegram не підключено",
    telegramLinkedAs: "Обліковий запис Telegram",
    telegramGenerate: "Створити посилання",
    telegramRegenerate: "Створити нове посилання",
    telegramUnlink: "Від'єднати Telegram",
    telegramOpen: "Відкрити Telegram",
    telegramCopy: "Скопіювати посилання",
    telegramCopyToken: "Скопіювати токен",
    telegramCopied: "Скопійовано",
    telegramExpires: "Посилання дійсне до",
    telegramManualStart: "Відкрийте свого бота та надішліть команду /start із цим токеном:",
    telegramRefresh: "Оновити статус",
    telegramLoadError: "Не вдалося завантажити статус Telegram.",
    telegramActionError: "Не вдалося виконати дію з Telegram.",
    telegramUnlinkConfirm: "Від'єднати Telegram від вашого облікового запису?",
  },
} satisfies Record<Locale, Record<string, string>>;

export function App() {
  const [locale, setLocale] = useState<Locale>(() => readStoredValue("locale", "ru") as Locale);
  const [authStatus, setAuthStatus] = useState<"loading" | "unauthenticated" | "authenticated">("loading");
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginPending, setLoginPending] = useState(false);
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
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  const [updatingTransactionId, setUpdatingTransactionId] = useState<string | null>(null);
  const [telegramStatus, setTelegramStatus] = useState<TelegramLinkStatus | null>(null);
  const [telegramLink, setTelegramLink] = useState<TelegramLinkToken | null>(null);
  const [telegramPending, setTelegramPending] = useState(false);
  const [telegramError, setTelegramError] = useState<string | null>(null);
  const [telegramCopied, setTelegramCopied] = useState(false);
  const [route, setRoute] = useState<AppRoute>(() => readRoute());
  const hasAutoLoadedRef = useRef(false);

  const handleAuthenticationFailure = useCallback((error: unknown) => {
    if (error instanceof Error && error.name === "AuthenticationRequiredError") {
      clearAccessToken();
      setCurrentUser(null);
      setTelegramStatus(null);
      setTelegramLink(null);
      setAuthStatus("unauthenticated");
    }
  }, []);

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
    localStorage.setItem("locale", locale);
  }, [locale]);

  useEffect(() => {
    const onPopState = () => setRoute(readRoute());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    localStorage.removeItem("familyId");
    let cancelled = false;
    void (async () => {
      const accessToken = await refreshAccessToken();
      if (!accessToken) {
        if (!cancelled) setAuthStatus("unauthenticated");
        return;
      }
      try {
        const user = await getCurrentUser();
        if (!cancelled) {
          setCurrentUser(user);
          setLocale(user.language);
          setAuthStatus("authenticated");
        }
      } catch {
        clearAccessToken();
        if (!cancelled) setAuthStatus("unauthenticated");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (authStatus !== "authenticated") return;
    let cancelled = false;
    const loadStatus = async () => {
      try {
        const status = await getTelegramLinkStatus();
        if (!cancelled) {
          setTelegramStatus(status);
          setTelegramError(null);
          if (status.is_linked) setTelegramLink(null);
        }
      } catch (error) {
        if (!cancelled) {
          handleAuthenticationFailure(error);
          setTelegramError(errorMessage(error, t.telegramLoadError));
        }
      }
    };
    void loadStatus();
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") void loadStatus();
    };
    window.addEventListener("focus", refreshWhenVisible);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      cancelled = true;
      window.removeEventListener("focus", refreshWhenVisible);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [authStatus, t.telegramLoadError]);

  useEffect(() => {
    if (state.data && authStatus === "authenticated") {
      void loadTransactions(reviewOnly);
    }
  }, [reviewOnly, authStatus]);

  useEffect(() => {
    if (authStatus === "authenticated" && !hasAutoLoadedRef.current) {
      hasAutoLoadedRef.current = true;
      void loadDashboard();
    }
  }, [authStatus]);

  async function loadDashboard() {
    setState((current) => ({ status: "loading", data: current.data, error: null }));
    setTransactionsState((current) => ({ status: "loading", data: current.data, error: null }));
    await loadCategories();
    try {
      const url = buildFilteredUrl(apiUrl("/analytics/dashboard"), {
        occurredFrom,
        occurredTo,
        scope,
      });

      const response = await authenticatedFetch(url);
      if (!response.ok) {
        throw new Error(dashboardErrorMessage(response.status, t));
      }
      const data = (await response.json()) as Dashboard;
      setState({ status: "success", data, error: null });
    } catch (error) {
      handleAuthenticationFailure(error);
      setState((current) => ({
        status: "error",
        data: current.data,
        error: error instanceof TypeError ? t.networkError : errorMessage(error, t.unknownError),
      }));
    }

    await loadTransactions(reviewOnly);
  }

  async function loadCategories() {
    setCategoriesError(null);
    try {
      const data = await getCategories();
      setCategories(data.rows);
    } catch (error) {
      handleAuthenticationFailure(error);
      setCategories([]);
      setCategoriesError(error instanceof TypeError ? t.networkError : errorMessage(error, t.categoryLoadError));
    }
  }

  async function loadTransactions(onlyReview: boolean) {
    setTransactionsState((current) => ({ status: "loading", data: current.data, error: null }));
    try {
      const url = buildFilteredUrl(apiUrl("/transactions"), {
        occurredFrom,
        occurredTo,
        scope,
      });
      url.searchParams.set("limit", "20");
      if (onlyReview) {
        url.searchParams.set("needs_review", "true");
      }

      const response = await authenticatedFetch(url);
      if (!response.ok) {
        throw new Error(dashboardErrorMessage(response.status, t));
      }
      const data = (await response.json()) as TransactionList;
      setTransactionsState({ status: "success", data, error: null });
    } catch (error) {
      handleAuthenticationFailure(error);
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
    await patchTransaction(transactionId, { needs_review: false });
  }

  async function assignTransactionCategory(transactionId: string, categoryId: string) {
    if (!categoryId) {
      return;
    }
    await patchTransaction(transactionId, { category_id: categoryId, needs_review: false });
  }

  async function patchTransaction(
    transactionId: string,
    payload: { category_id?: string; needs_review?: boolean },
  ) {
    setUpdatingTransactionId(transactionId);
    try {
      const response = await authenticatedFetch(apiUrl(`/transactions/${transactionId}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(dashboardErrorMessage(response.status, t));
      }
      await loadDashboard();
    } catch (error) {
      handleAuthenticationFailure(error);
      setTransactionsState((current) => ({
        status: "error",
        data: current.data,
        error: error instanceof TypeError ? t.networkError : errorMessage(error, t.unknownError),
      }));
    } finally {
      setUpdatingTransactionId(null);
    }
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoginPending(true);
    setLoginError(null);
    try {
      await signIn(loginEmail, loginPassword);
      const user = await getCurrentUser();
      setCurrentUser(user);
      setLocale(user.language);
      setLoginPassword("");
      hasAutoLoadedRef.current = false;
      setAuthStatus("authenticated");
    } catch (error) {
      clearAccessToken();
      setLoginError(error instanceof TypeError ? t.networkError : errorMessage(error, t.loginError));
    } finally {
      setLoginPending(false);
    }
  }

  async function handleLogout() {
    await signOut();
    hasAutoLoadedRef.current = false;
    setCurrentUser(null);
    setState({ status: "idle", data: null, error: null });
    setTransactionsState({ status: "idle", data: null, error: null });
    setCategories([]);
    setTelegramStatus(null);
    setTelegramLink(null);
    setTelegramError(null);
    setAuthStatus("unauthenticated");
  }

  async function handleCreateTelegramLink() {
    setTelegramPending(true);
    setTelegramError(null);
    setTelegramCopied(false);
    try {
      const link = await createTelegramLink();
      setTelegramLink(link);
    } catch (error) {
      handleAuthenticationFailure(error);
      setTelegramError(errorMessage(error, t.telegramActionError));
    } finally {
      setTelegramPending(false);
    }
  }

  async function refreshTelegramStatus() {
    try {
      const status = await getTelegramLinkStatus();
      setTelegramStatus(status);
      setTelegramError(null);
      if (status.is_linked) setTelegramLink(null);
    } catch (error) {
      handleAuthenticationFailure(error);
      setTelegramError(errorMessage(error, t.telegramLoadError));
    }
  }

  async function handleUnlinkTelegram() {
    if (!window.confirm(t.telegramUnlinkConfirm)) return;
    setTelegramPending(true);
    setTelegramError(null);
    try {
      await deleteTelegramLink();
      setTelegramStatus({ is_linked: false, username: null, first_name: null, linked_at: null });
      setTelegramLink(null);
    } catch (error) {
      handleAuthenticationFailure(error);
      setTelegramError(errorMessage(error, t.telegramActionError));
    } finally {
      setTelegramPending(false);
    }
  }

  async function handleCopyTelegramValue(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setTelegramCopied(true);
    } catch {
      setTelegramError(t.telegramActionError);
    }
  }

  function navigateTo(page: AppPage, batchId?: string) {
    const url = new URL(window.location.href);
    url.searchParams.set("page", page);
    if (page === "import" && batchId) url.searchParams.set("batch", batchId);
    else url.searchParams.delete("batch");
    window.history.pushState({}, "", `${url.pathname}${url.search}${url.hash}`);
    setRoute({ page, ...(page === "import" && batchId ? { batchId } : {}) });
  }

  const dashboard = state.data;
  const chartRows = useMemo(() => toChartRows(dashboard?.timeline.rows ?? []), [dashboard]);

  if (authStatus === "loading") {
    return (
      <main className="app-shell">
        <section className="empty-state">
          <RefreshCw className="spin" />
          <h2>{t.loading}</h2>
        </section>
      </main>
    );
  }

  if (authStatus === "unauthenticated") {
    return (
      <main className="app-shell auth-shell">
        <header className="topbar">
          <div>
            <p className="eyebrow">Family Cash Flow</p>
            <h1>{t.loginTitle}</h1>
            <p className="subtitle">{t.loginHelp}</p>
          </div>
          <label className="language-control">
            <span>{t.language}</span>
            <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
              <option value="ru">RU</option>
              <option value="uk">UA</option>
            </select>
          </label>
        </header>
        <form className="login-form" onSubmit={handleLogin}>
          <label className="field">
            <span>{t.email}</span>
            <input
              autoComplete="username"
              required
              type="email"
              value={loginEmail}
              onChange={(event) => setLoginEmail(event.target.value)}
            />
          </label>
          <label className="field">
            <span>{t.password}</span>
            <input
              autoComplete="current-password"
              required
              type="password"
              value={loginPassword}
              onChange={(event) => setLoginPassword(event.target.value)}
            />
          </label>
          {loginError && <p className="table-error">{loginError}</p>}
          <button className="primary-button" disabled={loginPending} type="submit">
            {loginPending ? <RefreshCw className="spin" /> : null}
            <span>{loginPending ? t.loading : t.signIn}</span>
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Family Cash Flow</p>
          <h1>{route.page === "dashboard" ? t.title : route.page === "transactions" ? t.navTransactions : route.page === "import" ? t.navImport : t.telegramTitle}</h1>
          <p className="subtitle">{t.account}: {currentUser?.family_name} · {currentUser?.display_name}</p>
        </div>
        <div className="account-controls">
          <label className="language-control">
            <span>{t.language}</span>
            <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
              <option value="ru">RU</option>
              <option value="uk">UA</option>
            </select>
          </label>
          <button className="secondary-button" onClick={() => void handleLogout()} type="button">
            {t.signOut}
          </button>
        </div>
      </header>

      <nav className="app-navigation" aria-label={locale === "uk" ? "Навігація" : "Навигация"}>
        <button
          aria-current={route.page === "dashboard" ? "page" : undefined}
          className={route.page === "dashboard" ? "is-active" : ""}
          onClick={() => navigateTo("dashboard")}
          type="button"
        >
          {t.navDashboard}
        </button>
        <button
          aria-current={route.page === "transactions" ? "page" : undefined}
          className={route.page === "transactions" ? "is-active" : ""}
          onClick={() => navigateTo("transactions")}
          type="button"
        >
          {t.navTransactions}
        </button>
        <button
          aria-current={route.page === "import" ? "page" : undefined}
          className={route.page === "import" ? "is-active" : ""}
          onClick={() => navigateTo("import")}
          type="button"
        >
          {t.navImport}
        </button>
        <button
          aria-current={route.page === "account" ? "page" : undefined}
          className={route.page === "account" ? "is-active" : ""}
          onClick={() => navigateTo("account")}
          type="button"
        >
          {t.navAccount}
        </button>
      </nav>

      {route.page === "transactions" && (
        <TransactionsPage
          locale={locale}
          onAuthFailure={handleAuthenticationFailure}
          onTransactionsChanged={() => void loadDashboard()}
        />
      )}

      {route.page === "import" && (
        <ImportPage
          batchId={route.batchId}
          locale={locale}
          onAuthFailure={handleAuthenticationFailure}
          onBatchIdChange={(batchId) => navigateTo("import", batchId)}
          onGoDashboard={() => {
            navigateTo("dashboard");
            void loadDashboard();
          }}
        />
      )}

      {route.page === "account" && <section className="panel telegram-panel" aria-labelledby="telegram-heading">
        <div className="telegram-heading">
          <div>
            <p className="eyebrow">{t.telegramTitle}</p>
            <h2 id="telegram-heading">
              {telegramStatus?.is_linked ? t.telegramLinked : t.telegramNotLinked}
            </h2>
          </div>
          <button
            className="secondary-button"
            disabled={telegramPending}
            onClick={() => void refreshTelegramStatus()}
            type="button"
          >
            {t.telegramRefresh}
          </button>
        </div>
        {telegramStatus?.is_linked ? (
          <div className="telegram-actions">
            <p>
              {t.telegramLinkedAs}: {telegramStatus.username ? `@${telegramStatus.username}` : telegramStatus.first_name ?? "—"}
            </p>
            <button className="secondary-button" disabled={telegramPending} onClick={() => void handleUnlinkTelegram()} type="button">
              {t.telegramUnlink}
            </button>
          </div>
        ) : (
          <div className="telegram-actions">
            <button className="primary-button" disabled={telegramPending} onClick={() => void handleCreateTelegramLink()} type="button">
              {telegramPending ? <RefreshCw className="spin" /> : null}
              <span>{telegramLink ? t.telegramRegenerate : t.telegramGenerate}</span>
            </button>
            {telegramLink && (
              <div className="telegram-link-result">
                <p>{t.telegramExpires}: {formatTelegramExpiry(telegramLink.expires_at, locale)}</p>
                {telegramLink.telegram_url ? (
                  <div className="telegram-link-actions">
                    <a className="primary-button telegram-anchor" href={telegramLink.telegram_url} rel="noreferrer" target="_blank">
                      {t.telegramOpen}
                    </a>
                    <button className="secondary-button" onClick={() => void handleCopyTelegramValue(telegramLink.telegram_url!)} type="button">
                      {telegramCopied ? t.telegramCopied : t.telegramCopy}
                    </button>
                  </div>
                ) : (
                  <div className="telegram-manual-token">
                    <p>{t.telegramManualStart}</p>
                    <code>/start {telegramLink.token}</code>
                    <button className="secondary-button" onClick={() => void handleCopyTelegramValue(telegramLink.token)} type="button">
                      {telegramCopied ? t.telegramCopied : t.telegramCopyToken}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
        {telegramError && <p className="telegram-error" role="alert">{telegramError}</p>}
      </section>}

      {route.page === "dashboard" && <>
      <form className="filters" onSubmit={handleSubmit}>
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
            {categoriesError && <p className="table-error">{categoriesError}</p>}
            {transactionsState.status === "loading" && !transactionsState.data ? (
              <EmptyRows text={t.loading} />
            ) : (
              <TransactionsTable
                categories={categories}
                emptyText={reviewOnly ? t.reviewQueueEmpty : t.noRows}
                formatter={formatter}
                onAssignCategory={assignTransactionCategory}
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
      </>}
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
  categories,
  rows,
  total,
  formatter,
  emptyText,
  onAssignCategory,
  onMarkReviewed,
  t,
  updatingTransactionId,
}: {
  categories: CategoryOption[];
  rows: TransactionRow[];
  total: number;
  formatter: Intl.NumberFormat;
  emptyText: string;
  onAssignCategory: (transactionId: string, categoryId: string) => void;
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
                <>
                  <select
                    className="category-select"
                    disabled={updatingTransactionId === row.id || categories.length === 0}
                    onChange={(event) => onAssignCategory(row.id, event.target.value)}
                    value={row.category_id ?? ""}
                  >
                    <option value="">{t.chooseCategory}</option>
                    {categories.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                  <button
                    className="review-button"
                    disabled={updatingTransactionId === row.id}
                    onClick={() => onMarkReviewed(row.id)}
                    type="button"
                  >
                    {updatingTransactionId === row.id ? <RefreshCw className="spin" /> : <CheckCircle />}
                    <span>{updatingTransactionId === row.id ? t.updating : t.markReviewed}</span>
                  </button>
                </>
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
  href: string | URL,
  filters: { occurredFrom: string; occurredTo: string; scope: ScopeFilter },
) {
  const url = new URL(href);
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

function formatTelegramExpiry(value: string, locale: Locale): string {
  return new Intl.DateTimeFormat(locale === "uk" ? "uk-UA" : "ru-UA", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function readStoredValue(key: string, fallback: string) {
  if (typeof localStorage === "undefined") {
    return fallback;
  }
  return localStorage.getItem(key) ?? fallback;
}

function readRoute(): AppRoute {
  const params = new URLSearchParams(window.location.search);
  const page = params.get("page");
  if (page === "account") return { page: "account" };
  if (page === "transactions") return { page: "transactions" };
  if (page === "import") {
    const batchId = params.get("batch") ?? undefined;
    return { page: "import", ...(batchId ? { batchId } : {}) };
  }
  return { page: "dashboard" };
}
