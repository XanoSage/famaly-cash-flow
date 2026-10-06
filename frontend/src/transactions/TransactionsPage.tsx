import { useEffect, useState, type FormEvent } from "react";
import {
  createTransaction,
  deleteTransaction,
  getAccounts,
  getCategories,
  listTransactions,
  updateTransaction,
  type Account,
  type CategoryApiRow,
  type TransactionFilters,
  type TransactionRow,
  type TransactionScope,
} from "../api";
import { formatTransactionAmount, isoToLocalDateTime, localDateTimeToIso } from "./logic";

type Locale = "ru" | "uk";
type Props = {
  locale: Locale;
  onAuthFailure: (error: unknown) => void;
  onTransactionsChanged: () => void;
};
type DraftFilters = {
  date_from: string;
  date_to: string;
  account_id: string;
  category_id: string;
  scope: "" | TransactionScope;
  direction: "" | "expense" | "income";
  uncategorized: boolean;
  needs_review: boolean;
};

const PAGE_SIZE = 25;
const emptyFilters: DraftFilters = {
  date_from: "",
  date_to: "",
  account_id: "",
  category_id: "",
  scope: "",
  direction: "",
  uncategorized: false,
  needs_review: false,
};

const copy = {
  ru: {
    title: "Операции",
    subtitle: "Все операции семьи, включая ручные записи и импортированные выписки.",
    add: "Добавить операцию",
    edit: "Изменить",
    remove: "Удалить",
    removeConfirm: "Удалить эту операцию? Она исчезнет из аналитики, но останется в истории.",
    createExpense: "Расход",
    createIncome: "Доход",
    amount: "Сумма",
    direction: "Тип операции",
    occurred: "Дата и время",
    merchant: "Описание / место",
    account: "Счёт",
    category: "Категория",
    subcategory: "Подкатегория",
    scope: "Слой",
    family: "Семья",
    personal: "Личное",
    work: "ФОП",
    incomeType: "Тип дохода",
    income: "Доход",
    refund: "Возврат",
    debt: "Долг / заём",
    other: "Другое",
    comment: "Комментарий",
    save: "Сохранить",
    cancel: "Отмена",
    dateFrom: "С даты",
    dateTo: "По дату",
    allAccounts: "Все счета",
    allCategories: "Все категории",
    allDirections: "Все операции",
    expenses: "Расходы",
    incomes: "Доходы",
    allScopes: "Все слои",
    uncategorized: "Без категории",
    review: "Требуют проверки",
    filter: "Применить фильтры",
    reset: "Сбросить",
    date: "Дата",
    details: "Описание",
    categoryColumn: "Категория",
    accountColumn: "Счёт",
    scopeColumn: "Слой",
    amountColumn: "Сумма",
    empty: "Операций не найдено.",
    loading: "Загружаю операции...",
    previous: "Назад",
    next: "Дальше",
    page: "Страница",
    of: "из",
    loadingOptions: "Загружаю счета и категории...",
    loadError: "Не удалось загрузить операции.",
    optionsError: "Не удалось загрузить счета или категории.",
    mutationError: "Не удалось сохранить операцию.",
    noCategory: "Без категории",
    reviewBadge: "проверить",
    transfer: "Перевод",
    familyScope: "Семья",
    personalScope: "Личное",
    workScope: "ФОП",
    commentColumn: "Комментарий",
  },
  uk: {
    title: "Операції",
    subtitle: "Усі операції родини, включно з ручними записами та імпортованими виписками.",
    add: "Додати операцію",
    edit: "Змінити",
    remove: "Видалити",
    removeConfirm: "Видалити цю операцію? Вона зникне з аналітики, але залишиться в історії.",
    createExpense: "Витрата",
    createIncome: "Дохід",
    amount: "Сума",
    direction: "Тип операції",
    occurred: "Дата і час",
    merchant: "Опис / місце",
    account: "Рахунок",
    category: "Категорія",
    subcategory: "Підкатегорія",
    scope: "Шар",
    family: "Родина",
    personal: "Особисте",
    work: "ФОП",
    incomeType: "Тип доходу",
    income: "Дохід",
    refund: "Повернення",
    debt: "Борг / позика",
    other: "Інше",
    comment: "Коментар",
    save: "Зберегти",
    cancel: "Скасувати",
    dateFrom: "З дати",
    dateTo: "До дати",
    allAccounts: "Усі рахунки",
    allCategories: "Усі категорії",
    allDirections: "Усі операції",
    expenses: "Витрати",
    incomes: "Доходи",
    allScopes: "Усі шари",
    uncategorized: "Без категорії",
    review: "Потребують перевірки",
    filter: "Застосувати фільтри",
    reset: "Скинути",
    date: "Дата",
    details: "Опис",
    categoryColumn: "Категорія",
    accountColumn: "Рахунок",
    scopeColumn: "Шар",
    amountColumn: "Сума",
    empty: "Операцій не знайдено.",
    loading: "Завантажую операції...",
    previous: "Назад",
    next: "Далі",
    page: "Сторінка",
    of: "з",
    loadingOptions: "Завантажую рахунки та категорії...",
    loadError: "Не вдалося завантажити операції.",
    optionsError: "Не вдалося завантажити рахунки або категорії.",
    mutationError: "Не вдалося зберегти операцію.",
    noCategory: "Без категорії",
    reviewBadge: "перевірити",
    transfer: "Переказ",
    familyScope: "Родина",
    personalScope: "Особисте",
    workScope: "ФОП",
    commentColumn: "Коментар",
  },
} satisfies Record<Locale, Record<string, string>>;

const flowLabels: Record<Locale, Record<string, string>> = {
  ru: {
    purchase: "Покупка",
    cash_withdrawal: "Снятие наличных",
    cash_expense: "Расход наличными",
    transfer_to_own_account: "Перевод между своими счетами",
    transfer_to_savings: "Перевод в накопления",
    transfer_to_wife: "Перевод супруге",
    person_transfer: "Перевод человеку",
    requisites_payment: "Платёж по реквизитам",
    refund: "Возврат",
    income: "Доход",
    subscription: "Подписка",
    work_fop: "ФОП",
    other: "Другое",
  },
  uk: {
    purchase: "Купівля",
    cash_withdrawal: "Зняття готівки",
    cash_expense: "Витрата готівкою",
    transfer_to_own_account: "Переказ між своїми рахунками",
    transfer_to_savings: "Переказ до заощаджень",
    transfer_to_wife: "Переказ дружині",
    person_transfer: "Переказ людині",
    requisites_payment: "Платіж за реквізитами",
    refund: "Повернення",
    income: "Дохід",
    subscription: "Підписка",
    work_fop: "ФОП",
    other: "Інше",
  },
};

export function TransactionsPage({ locale, onAuthFailure, onTransactionsChanged }: Props) {
  const t = copy[locale];
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<CategoryApiRow[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [filters, setFilters] = useState<DraftFilters>(emptyFilters);
  const [appliedFilters, setAppliedFilters] = useState<DraftFilters>(emptyFilters);
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<TransactionRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<TransactionRow | null>(null);
  const [saving, setSaving] = useState(false);
  const [rowBusy, setRowBusy] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setOptionsLoading(true);
    void Promise.all([getAccounts(), getCategories()])
      .then(([accountResponse, categoryResponse]) => {
        if (!active) return;
        setAccounts(accountResponse.rows.filter((account) => account.is_active));
        setCategories(categoryResponse.rows);
        setOptionsError(null);
      })
      .catch((loadError: unknown) => {
        if (!active) return;
        onAuthFailure(loadError);
        setOptionsError(errorMessage(loadError, t.optionsError));
      })
      .finally(() => {
        if (active) setOptionsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [onAuthFailure, t.optionsError]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void listTransactions(toApiFilters(appliedFilters, offset))
      .then((response) => {
        if (!active) return;
        setRows(response.rows);
        setTotal(response.total);
        if (response.total > 0 && offset >= response.total) {
          setOffset(Math.max(0, Math.floor((response.total - 1) / PAGE_SIZE) * PAGE_SIZE));
        }
      })
      .catch((loadError: unknown) => {
        if (!active) return;
        onAuthFailure(loadError);
        setError(errorMessage(loadError, t.loadError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [appliedFilters, offset, onAuthFailure, t.loadError]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
    setAppliedFilters({ ...filters });
  }

  async function refreshAfterMutation(nextOffset: number) {
    const response = await listTransactions(toApiFilters(appliedFilters, nextOffset));
    setOffset(nextOffset);
    setRows(response.rows);
    setTotal(response.total);
    if (response.total > 0 && nextOffset >= response.total) {
      const correctedOffset = Math.max(0, Math.floor((response.total - 1) / PAGE_SIZE) * PAGE_SIZE);
      setOffset(correctedOffset);
      const corrected = await listTransactions(toApiFilters(appliedFilters, correctedOffset));
      setRows(corrected.rows);
      setTotal(corrected.total);
    }
    onTransactionsChanged();
  }

  async function saveTransaction(payload: Parameters<typeof createTransaction>[0], transactionId?: string) {
    setSaving(true);
    setError(null);
    try {
      if (transactionId) await updateTransaction(transactionId, payload);
      else await createTransaction(payload);
      setEditorOpen(false);
      setEditing(null);
      await refreshAfterMutation(transactionId ? offset : 0);
    } catch (mutationError) {
      onAuthFailure(mutationError);
      setError(errorMessage(mutationError, t.mutationError));
      throw mutationError;
    } finally {
      setSaving(false);
    }
  }

  async function removeTransaction(transaction: TransactionRow) {
    if (!window.confirm(t.removeConfirm)) return;
    setRowBusy(transaction.id);
    setError(null);
    try {
      await deleteTransaction(transaction.id);
      await refreshAfterMutation(offset);
    } catch (mutationError) {
      onAuthFailure(mutationError);
      setError(errorMessage(mutationError, t.mutationError));
    } finally {
      setRowBusy(null);
    }
  }

  return (
    <section className="transactions-page" aria-labelledby="transactions-title">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Family Cash Flow</p>
          <h2 id="transactions-title">{t.title}</h2>
          <p className="subtitle">{t.subtitle}</p>
        </div>
        <button
          className="primary-button"
          disabled={optionsLoading || accounts.length === 0}
          onClick={() => {
            setEditing(null);
            setEditorOpen(true);
          }}
          type="button"
        >
          <span>{t.add}</span>
        </button>
      </div>

      {optionsError && <p className="table-error" role="alert">{optionsError}</p>}
      {error && <p className="table-error" role="alert">{error}</p>}

      <form className="transactions-filters panel" onSubmit={applyFilters}>
        <label className="field">
          <span>{t.dateFrom}</span>
          <input type="date" value={filters.date_from} onChange={(event) => setFilters({ ...filters, date_from: event.target.value })} />
        </label>
        <label className="field">
          <span>{t.dateTo}</span>
          <input type="date" value={filters.date_to} onChange={(event) => setFilters({ ...filters, date_to: event.target.value })} />
        </label>
        <label className="field">
          <span>{t.account}</span>
          <select value={filters.account_id} onChange={(event) => setFilters({ ...filters, account_id: event.target.value })}>
            <option value="">{t.allAccounts}</option>
            {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
          </select>
        </label>
        <label className="field">
          <span>{t.category}</span>
          <select value={filters.category_id} onChange={(event) => setFilters({ ...filters, category_id: event.target.value })}>
            <option value="">{t.allCategories}</option>
            {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
        </label>
        <label className="field">
          <span>{t.scope}</span>
          <select value={filters.scope} onChange={(event) => setFilters({ ...filters, scope: event.target.value as DraftFilters["scope"] })}>
            <option value="">{t.allScopes}</option>
            <option value="family">{t.family}</option>
            <option value="personal_main_user">{t.personal}</option>
            <option value="work_fop">{t.work}</option>
          </select>
        </label>
        <label className="field">
          <span>{t.details}</span>
          <select value={filters.direction} onChange={(event) => setFilters({ ...filters, direction: event.target.value as DraftFilters["direction"] })}>
            <option value="">{t.allDirections}</option>
            <option value="expense">{t.expenses}</option>
            <option value="income">{t.incomes}</option>
          </select>
        </label>
        <label className="toggle-control">
          <input type="checkbox" checked={filters.uncategorized} onChange={(event) => setFilters({ ...filters, uncategorized: event.target.checked })} />
          <span>{t.uncategorized}</span>
        </label>
        <label className="toggle-control">
          <input type="checkbox" checked={filters.needs_review} onChange={(event) => setFilters({ ...filters, needs_review: event.target.checked })} />
          <span>{t.review}</span>
        </label>
        <div className="transactions-filter-actions">
          <button className="primary-button" type="submit">{t.filter}</button>
          <button className="secondary-button" type="button" onClick={() => { setFilters(emptyFilters); setAppliedFilters(emptyFilters); setOffset(0); }}>{t.reset}</button>
        </div>
      </form>

      {optionsLoading && <p className="table-summary">{t.loadingOptions}</p>}
      <div className="transactions-block">
        <div className="transactions-table full-transactions-table">
          <div className="transactions-head">
            <span>{t.date}</span><span>{t.details}</span><span>{t.categoryColumn}</span>
            <span>{t.accountColumn}</span><span>{t.scopeColumn}</span><span>{t.amountColumn}</span><span />
          </div>
          {loading ? <p className="empty-rows">{t.loading}</p> : rows.length === 0 ? <p className="empty-rows">{t.empty}</p> : rows.map((row) => (
            <TransactionTableRow
              key={row.id}
              locale={locale}
              onDelete={() => void removeTransaction(row)}
              onEdit={() => { setEditing(row); setEditorOpen(true); }}
              row={row}
              t={t}
              busy={rowBusy === row.id}
            />
          ))}
        </div>
        <div className="transactions-pagination">
          <button className="secondary-button" disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} type="button">{t.previous}</button>
          <span>{t.page} {currentPage} {t.of} {totalPages} · {total}</span>
          <button className="secondary-button" disabled={loading || offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)} type="button">{t.next}</button>
        </div>
      </div>

      {editorOpen && (
        <TransactionEditor
          accounts={accounts}
          categories={categories}
          initial={editing}
          locale={locale}
          onCancel={() => { setEditorOpen(false); setEditing(null); }}
          onSave={saveTransaction}
          saving={saving}
          t={t}
        />
      )}
    </section>
  );
}

function TransactionTableRow({
  row, locale, t, busy, onEdit, onDelete,
}: {
  row: TransactionRow;
  locale: Locale;
  t: Record<string, string>;
  busy: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const directionName = row.direction === "income" ? t.incomes : row.direction === "transfer" ? t.transfer : t.expenses;
  return (
    <article className="full-transaction-row">
      <time dateTime={row.occurred_at}>{new Intl.DateTimeFormat(locale === "uk" ? "uk-UA" : "ru-UA", { dateStyle: "short", timeStyle: "short" }).format(new Date(row.occurred_at))}</time>
      <div className="transaction-main">
        <strong>{row.display_description ?? row.description_raw ?? row.flow_type}</strong>
        <span>{directionName} · {flowLabels[locale][row.flow_type] ?? row.flow_type}{row.needs_review ? ` · ${t.reviewBadge}` : ""}</span>
        {row.comment && <small>{row.comment}</small>}
      </div>
      <span>{row.category_name ?? t.noCategory}{row.subcategory_name ? ` / ${row.subcategory_name}` : ""}</span>
      <span>{row.account_name}</span>
      <span className="scope-pill">{scopeLabel(row.scope, t)}</span>
      <b className={row.amount.startsWith("-") ? "amount-negative" : "amount-positive"}>{formatTransactionAmount(row.amount, row.currency, locale)}</b>
      <div className="full-transaction-actions">
        {row.direction !== "transfer" && <button className="review-button" disabled={busy} onClick={onEdit} type="button">{t.edit}</button>}
        <button className="secondary-button danger-button" disabled={busy} onClick={onDelete} type="button">{busy ? "…" : t.remove}</button>
      </div>
    </article>
  );
}

function TransactionEditor({
  accounts, categories, initial, locale, t, saving, onCancel, onSave,
}: {
  accounts: Account[];
  categories: CategoryApiRow[];
  initial: TransactionRow | null;
  locale: Locale;
  t: Record<string, string>;
  saving: boolean;
  onCancel: () => void;
  onSave: (payload: Parameters<typeof createTransaction>[0], transactionId?: string) => Promise<void>;
}) {
  const [direction, setDirection] = useState<"expense" | "income">(initial?.direction === "income" ? "income" : "expense");
  const [amount, setAmount] = useState(initial ? unsignedAmount(initial.amount) : "");
  const [accountId, setAccountId] = useState(
    initial?.account_id ?? accounts.find((account) => account.is_default)?.id ?? accounts[0]?.id ?? "",
  );
  const [occurredAt, setOccurredAt] = useState(initial ? isoToLocalDateTime(initial.occurred_at) : isoToLocalDateTime(new Date().toISOString()));
  const [merchantName, setMerchantName] = useState(initial?.display_description ?? initial?.description_raw ?? "");
  const [categoryId, setCategoryId] = useState(initial?.category_id ?? "");
  const [subcategoryId, setSubcategoryId] = useState(initial?.subcategory_id ?? "");
  const [scope, setScope] = useState<TransactionScope>(initial?.scope ?? "family");
  const [incomeType, setIncomeType] = useState(initial?.income_type ?? "income");
  const [comment, setComment] = useState(initial?.comment ?? "");
  const [formError, setFormError] = useState<string | null>(null);
  const selectedCategory = categories.find((category) => category.id === categoryId);
  const dateLocale = locale === "uk" ? "uk-UA" : "ru-UA";

  useEffect(() => {
    if (!accountId && accounts.length > 0) {
      setAccountId(accounts.find((account) => account.is_default)?.id ?? accounts[0].id);
    }
  }, [accountId, accounts]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    try {
      const payload = {
        direction,
        amount: amount.trim(),
        account_id: accountId,
        occurred_at: localDateTimeToIso(occurredAt),
        merchant_name: merchantName.trim() || null,
        category_id: categoryId || null,
        subcategory_id: subcategoryId || null,
        scope,
        comment: comment.trim() || null,
        ...(direction === "income" ? { income_type: incomeType } : {}),
      } as const;
      await onSave(payload, initial?.id);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : t.mutationError);
    }
  }

  return (
    <div className="transaction-modal-backdrop" role="presentation">
      <section className="transaction-editor panel" aria-labelledby="transaction-editor-title" aria-modal="true" role="dialog">
        <div className="page-heading">
          <h2 id="transaction-editor-title">{initial ? t.edit : t.add}</h2>
          <button className="secondary-button" onClick={onCancel} type="button">{t.cancel}</button>
        </div>
        <form className="transaction-editor-form" onSubmit={(event) => void submit(event)}>
          <label className="field"><span>{t.direction}</span><select value={direction} onChange={(event) => setDirection(event.target.value as "expense" | "income")}>
            <option value="expense">{t.createExpense}</option><option value="income">{t.createIncome}</option>
          </select></label>
          <label className="field"><span>{t.amount}</span><input inputMode="decimal" min="0.01" max="999999999999.99" pattern="[0-9]+([.,][0-9]{1,2})?" required value={amount} onChange={(event) => setAmount(event.target.value.replace(",", "."))} /></label>
          <label className="field"><span>{t.occurred}</span><input required type="datetime-local" value={occurredAt} onChange={(event) => setOccurredAt(event.target.value)} /></label>
          <label className="field"><span>{t.account}</span><select required value={accountId} onChange={(event) => setAccountId(event.target.value)}>{accounts.map((account) => <option key={account.id} value={account.id}>{account.name} · {account.currency}</option>)}</select></label>
          <label className="field"><span>{t.merchant}</span><input maxLength={255} value={merchantName} onChange={(event) => setMerchantName(event.target.value)} /></label>
          <label className="field"><span>{t.category}</span><select value={categoryId} onChange={(event) => { setCategoryId(event.target.value); setSubcategoryId(""); }}><option value="">{t.noCategory}</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
          <label className="field"><span>{t.subcategory}</span><select disabled={!selectedCategory?.subcategories.length} value={subcategoryId} onChange={(event) => setSubcategoryId(event.target.value)}><option value="">—</option>{selectedCategory?.subcategories.map((subcategory) => <option key={subcategory.id} value={subcategory.id}>{subcategory.name}</option>)}</select></label>
          <label className="field"><span>{t.scope}</span><select value={scope} onChange={(event) => setScope(event.target.value as TransactionScope)}><option value="family">{t.family}</option><option value="personal_main_user">{t.personal}</option><option value="work_fop">{t.work}</option></select></label>
          {direction === "income" && <label className="field"><span>{t.incomeType}</span><select value={incomeType} onChange={(event) => setIncomeType(event.target.value)}><option value="income">{t.income}</option><option value="refund">{t.refund}</option><option value="debt">{t.debt}</option><option value="other">{t.other}</option></select></label>}
          <label className="field editor-comment"><span>{t.comment}</span><textarea maxLength={4000} rows={3} value={comment} onChange={(event) => setComment(event.target.value)} /></label>
          {formError && <p className="table-error" role="alert">{formError}</p>}
          <div className="transaction-editor-actions">
            <button className="secondary-button" onClick={onCancel} type="button">{t.cancel}</button>
            <button className="primary-button" disabled={saving || !accountId} type="submit">{saving ? t.loading : t.save}</button>
          </div>
        </form>
      </section>
    </div>
  );
}

function toApiFilters(filters: DraftFilters, offset: number): TransactionFilters {
  return {
    offset,
    limit: PAGE_SIZE,
    ...(filters.date_from ? { date_from: filters.date_from } : {}),
    ...(filters.date_to ? { date_to: filters.date_to } : {}),
    ...(filters.account_id ? { account_id: filters.account_id } : {}),
    ...(filters.category_id ? { category_id: filters.category_id } : {}),
    ...(filters.scope ? { scope: filters.scope } : {}),
    ...(filters.direction ? { direction: filters.direction } : {}),
    ...(filters.uncategorized ? { uncategorized: true } : {}),
    ...(filters.needs_review ? { needs_review: true } : {}),
  };
}

function unsignedAmount(amount: string) {
  return amount.startsWith("-") ? amount.slice(1) : amount;
}

function scopeLabel(scope: TransactionScope, t: Record<string, string>) {
  if (scope === "family") return t.familyScope;
  if (scope === "personal_main_user") return t.personalScope;
  return t.workScope;
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}
