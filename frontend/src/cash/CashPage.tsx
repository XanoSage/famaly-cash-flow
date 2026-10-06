import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  createCashExpense,
  createCashWithdrawal,
  ensureCashWallet,
  getAccounts,
  getCashSummary,
  getCategories,
  type Account,
  type CashSummary,
  type CategoryApiRow,
  type TransactionScope,
} from "../api";
import { formatTransactionAmount, isoToLocalDateTime, localDateTimeToIso } from "../transactions/logic";

type Locale = "ru" | "uk";
type Props = {
  locale: Locale;
  onAuthFailure: (error: unknown) => void;
  onTransactionsChanged: () => void;
};

const copy = {
  ru: {
    title: "Наличные",
    subtitle: "Приблизительный остаток наличных в семейном кошельке.",
    approximate: "Баланс приблизительный и может отличаться от наличных на руках.",
    transferNote: "Снятие наличных — это перевод на кошелек, а не семейный расход.",
    setupTitle: "Создайте семейный кошелек наличных",
    setup: "Создать кошелек",
    balance: "Остаток",
    withdraw: "Снять наличные",
    expense: "Расход наличными",
    amount: "Сумма",
    date: "Дата и время",
    source: "Снять со счета",
    chooseSource: "Выберите счет",
    description: "Описание / место",
    category: "Категория",
    noCategory: "Без категории",
    subcategory: "Подкатегория",
    scope: "Слой",
    family: "Семья",
    personal: "Личное",
    work: "ФОП",
    comment: "Комментарий",
    saveWithdrawal: "Записать снятие",
    saveExpense: "Записать расход",
    recent: "Последние движения наличных",
    empty: "Пока нет операций с наличными.",
    loading: "Загружаю наличные…",
    saving: "Сохраняю…",
    loadError: "Не удалось загрузить наличный кошелек.",
    saveError: "Не удалось сохранить операцию.",
    noSources: "Нет активного счета в валюте кошелька для снятия наличных.",
    wallet: "Семейный кошелек",
  },
  uk: {
    title: "Готівка",
    subtitle: "Орієнтовний залишок готівки у спільному гаманці родини.",
    approximate: "Баланс приблизний і може відрізнятися від готівки на руках.",
    transferNote: "Зняття готівки — це переказ до гаманця, а не витрата родини.",
    setupTitle: "Створіть спільний гаманець готівки",
    setup: "Створити гаманець",
    balance: "Залишок",
    withdraw: "Зняти готівку",
    expense: "Витрата готівкою",
    amount: "Сума",
    date: "Дата й час",
    source: "Зняти з рахунку",
    chooseSource: "Оберіть рахунок",
    description: "Опис / місце",
    category: "Категорія",
    noCategory: "Без категорії",
    subcategory: "Підкатегорія",
    scope: "Шар",
    family: "Родина",
    personal: "Особисте",
    work: "ФОП",
    comment: "Коментар",
    saveWithdrawal: "Записати зняття",
    saveExpense: "Записати витрату",
    recent: "Останні рухи готівки",
    empty: "Операцій із готівкою ще немає.",
    loading: "Завантажуємо готівку…",
    saving: "Зберігаємо…",
    loadError: "Не вдалося завантажити гаманець готівки.",
    saveError: "Не вдалося зберегти операцію.",
    noSources: "Немає активного рахунку у валюті гаманця для зняття готівки.",
    wallet: "Спільний гаманець",
  },
} satisfies Record<Locale, Record<string, string>>;

export function CashPage({ locale, onAuthFailure, onTransactionsChanged }: Props) {
  const t = copy[locale];
  const [summary, setSummary] = useState<CashSummary | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<CategoryApiRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [sourceAccountId, setSourceAccountId] = useState("");
  const [withdrawAt, setWithdrawAt] = useState(() => isoToLocalDateTime(new Date().toISOString()));
  const [withdrawDescription, setWithdrawDescription] = useState("");
  const [withdrawComment, setWithdrawComment] = useState("");
  const [expenseAmount, setExpenseAmount] = useState("");
  const [expenseAt, setExpenseAt] = useState(() => isoToLocalDateTime(new Date().toISOString()));
  const [expenseDescription, setExpenseDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [subcategoryId, setSubcategoryId] = useState("");
  const [scope, setScope] = useState<TransactionScope>("family");
  const [expenseComment, setExpenseComment] = useState("");

  const selectedCategory = categories.find((category) => category.id === categoryId);
  const sourceAccounts = useMemo(
    () => accounts.filter((account) => account.type !== "cash" && account.is_active && account.currency === summary?.wallet?.currency),
    [accounts, summary?.wallet?.currency],
  );

  async function loadLedger() {
    setLoading(true);
    setError(null);
    try {
      const [cashSummary, accountResponse, categoryResponse] = await Promise.all([
        getCashSummary(),
        getAccounts(),
        getCategories(),
      ]);
      setSummary(cashSummary);
      setAccounts(accountResponse.rows.filter((account) => account.is_active));
      setCategories(categoryResponse.rows);
      setSourceAccountId((current) => current || accountResponse.rows.find((account) =>
        account.type !== "cash"
        && account.is_active
        && (!cashSummary.wallet || account.currency === cashSummary.wallet.currency),
      )?.id || "");
    } catch (loadError) {
      onAuthFailure(loadError);
      setError(errorMessage(loadError, t.loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadLedger();
  }, []);

  async function setupWallet() {
    setSaving(true);
    setError(null);
    try {
      await ensureCashWallet();
      await loadLedger();
    } catch (mutationError) {
      onAuthFailure(mutationError);
      setError(errorMessage(mutationError, t.saveError));
    } finally {
      setSaving(false);
    }
  }

  async function submitWithdrawal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createCashWithdrawal({
        source_account_id: sourceAccountId,
        amount: withdrawAmount.trim(),
        occurred_at: localDateTimeToIso(withdrawAt),
        description: withdrawDescription.trim() || null,
        comment: withdrawComment.trim() || null,
      });
      setWithdrawAmount("");
      setWithdrawDescription("");
      setWithdrawComment("");
      await loadLedger();
      onTransactionsChanged();
    } catch (mutationError) {
      onAuthFailure(mutationError);
      setError(errorMessage(mutationError, t.saveError));
    } finally {
      setSaving(false);
    }
  }

  async function submitExpense(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createCashExpense({
        amount: expenseAmount.trim(),
        occurred_at: localDateTimeToIso(expenseAt),
        merchant_name: expenseDescription.trim() || null,
        category_id: categoryId || null,
        subcategory_id: subcategoryId || null,
        scope,
        comment: expenseComment.trim() || null,
      });
      setExpenseAmount("");
      setExpenseDescription("");
      setExpenseComment("");
      await loadLedger();
      onTransactionsChanged();
    } catch (mutationError) {
      onAuthFailure(mutationError);
      setError(errorMessage(mutationError, t.saveError));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="cash-page" aria-labelledby="cash-page-title">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Family Cash Flow</p>
          <h2 id="cash-page-title">{t.title}</h2>
          <p className="subtitle">{t.subtitle}</p>
        </div>
        {summary?.wallet && <div className="cash-balance panel">
          <span>{t.balance}</span>
          <strong>{formatTransactionAmount(summary.balance, summary.wallet.currency, locale)}</strong>
          <small>{t.approximate}</small>
        </div>}
      </div>

      {error && <p className="table-error" role="alert">{error}</p>}
      {loading && <p className="table-summary">{t.loading}</p>}

      {!loading && summary && !summary.wallet ? (
        <section className="cash-setup panel">
          <div>
            <h3>{t.setupTitle}</h3>
            <p className="subtitle">{t.approximate}</p>
          </div>
          <button className="primary-button" disabled={saving} onClick={() => void setupWallet()} type="button">
            {saving ? t.saving : t.setup}
          </button>
        </section>
      ) : summary?.wallet ? (
        <>
          <p className="cash-transfer-note">{t.transferNote}</p>
          <div className="cash-forms">
            <form className="cash-form panel" onSubmit={(event) => void submitWithdrawal(event)}>
              <h3>{t.withdraw}</h3>
              <label className="field"><span>{t.source}</span><select required value={sourceAccountId} onChange={(event) => setSourceAccountId(event.target.value)}>
                <option value="">{t.chooseSource}</option>
                {sourceAccounts.map((account) => <option key={account.id} value={account.id}>{account.name} · {account.currency}</option>)}
              </select></label>
              {sourceAccounts.length === 0 && <p className="table-summary">{t.noSources}</p>}
              <MoneyFields
                amount={withdrawAmount}
                date={withdrawAt}
                dateLabel={t.date}
                amountLabel={t.amount}
                onAmountChange={setWithdrawAmount}
                onDateChange={setWithdrawAt}
              />
              <label className="field"><span>{t.description}</span><input maxLength={255} value={withdrawDescription} onChange={(event) => setWithdrawDescription(event.target.value)} /></label>
              <label className="field"><span>{t.comment}</span><textarea maxLength={4000} rows={2} value={withdrawComment} onChange={(event) => setWithdrawComment(event.target.value)} /></label>
              <button className="primary-button" disabled={saving || !sourceAccountId} type="submit">{saving ? t.saving : t.saveWithdrawal}</button>
            </form>

            <form className="cash-form panel" onSubmit={(event) => void submitExpense(event)}>
              <h3>{t.expense}</h3>
              <MoneyFields
                amount={expenseAmount}
                date={expenseAt}
                dateLabel={t.date}
                amountLabel={t.amount}
                onAmountChange={setExpenseAmount}
                onDateChange={setExpenseAt}
              />
              <label className="field"><span>{t.description}</span><input maxLength={255} value={expenseDescription} onChange={(event) => setExpenseDescription(event.target.value)} /></label>
              <label className="field"><span>{t.category}</span><select aria-label={t.category} value={categoryId} onChange={(event) => { setCategoryId(event.target.value); setSubcategoryId(""); }}>
                <option value="">{t.noCategory}</option>
                {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
              </select></label>
              <label className="field"><span>{t.subcategory}</span><select aria-label={t.subcategory} disabled={!selectedCategory?.subcategories.length} value={subcategoryId} onChange={(event) => setSubcategoryId(event.target.value)}>
                <option value="">—</option>
                {selectedCategory?.subcategories.map((subcategory) => <option key={subcategory.id} value={subcategory.id}>{subcategory.name}</option>)}
              </select></label>
              <label className="field"><span>{t.scope}</span><select value={scope} onChange={(event) => setScope(event.target.value as TransactionScope)}>
                <option value="family">{t.family}</option>
                <option value="personal_main_user">{t.personal}</option>
                <option value="work_fop">{t.work}</option>
              </select></label>
              <label className="field"><span>{t.comment}</span><textarea maxLength={4000} rows={2} value={expenseComment} onChange={(event) => setExpenseComment(event.target.value)} /></label>
              <button className="primary-button" disabled={saving} type="submit">{saving ? t.saving : t.saveExpense}</button>
            </form>
          </div>

          <section className="cash-operations panel" aria-labelledby="cash-recent-title">
            <h3 id="cash-recent-title">{t.recent}</h3>
            {summary.recent_operations.length === 0 ? <p className="empty-rows">{t.empty}</p> : summary.recent_operations.map((operation) => (
              <article className="cash-operation" key={operation.id}>
                <time dateTime={operation.occurred_at}>{new Intl.DateTimeFormat(locale === "uk" ? "uk-UA" : "ru-UA", { dateStyle: "short", timeStyle: "short" }).format(new Date(operation.occurred_at))}</time>
                <div><strong>{operation.description ?? operation.flow_type}</strong><small>{operation.flow_type === "cash_withdrawal" ? t.withdraw : t.expense}</small></div>
                <b className={operation.amount.startsWith("-") ? "amount-negative" : "amount-positive"}>{formatTransactionAmount(operation.amount, operation.currency, locale)}</b>
              </article>
            ))}
          </section>
        </>
      ) : null}
    </section>
  );
}

function MoneyFields({
  amount, date, amountLabel, dateLabel, onAmountChange, onDateChange,
}: {
  amount: string;
  date: string;
  amountLabel: string;
  dateLabel: string;
  onAmountChange: (value: string) => void;
  onDateChange: (value: string) => void;
}) {
  return <>
    <label className="field"><span>{amountLabel}</span><input inputMode="decimal" min="0.01" max="999999999999.99" pattern="[0-9]+([.,][0-9]{1,2})?" required value={amount} onChange={(event) => onAmountChange(event.target.value.replace(",", "."))} /></label>
    <label className="field"><span>{dateLabel}</span><input required type="datetime-local" value={date} onChange={(event) => onDateChange(event.target.value)} /></label>
  </>;
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}
