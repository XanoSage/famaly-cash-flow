import { test as base, expect, type Locator, type Page } from "@playwright/test";
import { fileURLToPath } from "node:url";

const email = process.env.E2E_TEST_EMAIL ?? "";
const password = process.env.E2E_TEST_PASSWORD ?? "";
const fixturePath = fileURLToPath(new URL("./fixtures/synthetic-e2e-statement.xlsx", import.meta.url));

const test = base.extend<{ apiFailures: string[] }>({
  apiFailures: async ({ page }, use, testInfo) => {
    const failures: string[] = [];
    page.on("response", (response) => {
      if (response.status() < 400 || !response.url().includes("/api/v1/")) return;
      const request = response.request();
      const path = new URL(response.url()).pathname;
      if (
        response.status() === 401
        && request.method() === "POST"
        && path.endsWith("/auth/refresh")
      ) {
        return;
      }
      failures.push(
        `${response.status()} ${request.method()} ${safePath(response.url())}`,
      );
    });
    page.on("requestfailed", (request) => {
      if (!request.url().includes("/api/v1/")) return;
      failures.push(`request failed ${request.method()} ${safePath(request.url())}`);
    });

    await use(failures);
    if (testInfo.status !== testInfo.expectedStatus && failures.length > 0) {
      await testInfo.attach("api-failures.txt", {
        body: failures.join("\n"),
        contentType: "text/plain",
      });
    }
  },
});

test("authenticated Web MVP works from XLSX import through cash ledger", async ({ page, apiFailures }) => {
  test.setTimeout(120_000);
  void apiFailures;
  expect(email, "E2E_TEST_EMAIL must be set by the E2E environment").toMatch(/@example\.test$/);
  expect(password.length, "E2E_TEST_PASSWORD must be set by the E2E environment").toBeGreaterThanOrEqual(12);

  const refreshStatuses: number[] = [];
  page.on("response", (response) => {
    if (new URL(response.url()).pathname.endsWith("/auth/refresh")) {
      refreshStatuses.push(response.status());
    }
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Вход в Family Cash Flow" })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Пароль").fill(password);
  await page.getByRole("button", { name: "Войти" }).click();

  const familyContext = page.getByText("Семья: E2E Test Household · E2E Owner");
  await expect(familyContext).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Навигация" })).toBeVisible();

  // A full reload clears the in-memory access token. Continued access therefore uses
  // the browser's HttpOnly refresh cookie, without reading or exposing its value.
  await page.reload();
  await expect(familyContext).toBeVisible();
  expect(refreshStatuses).toContain(200);

  await page.getByRole("button", { name: "Импорт" }).click();
  await expect(page.getByRole("heading", { name: "Импорт выписки" })).toBeVisible();
  await page.getByLabel("Выбрать файл").setInputFiles(fixturePath);
  await page.getByRole("button", { name: "Загрузить и проверить" }).click();

  const summary = page
    .getByRole("region", { name: "Проверка операций" })
    .filter({ has: page.getByRole("heading", { name: "synthetic-e2e-statement.xlsx" }) });
  await expect(summary).toBeVisible();
  await expect(summaryMetric(summary, "Всего")).toHaveText("7");
  await expect(summaryMetric(summary, "Нужна проверка")).toHaveText("5");
  await expect(summaryMetric(summary, "Возможные дубли")).toHaveText("1");

  await page.getByRole("tab", { name: /Дубли/ }).click();
  const duplicateRow = importRow(page, "E2E Market");
  await expect(duplicateRow.getByText("Дубль", { exact: true })).toBeVisible();
  await expect(duplicateRow.getByText(/повторяет строку/)).toBeVisible();

  await page.getByRole("tab", { name: /Нужна проверка/ }).click();
  const newMerchantRow = importRow(page, "E2E New Merchant");
  await expect(newMerchantRow.getByText("Нужна проверка", { exact: true })).toBeVisible();
  await newMerchantRow.getByRole("button", { name: "Проверить" }).click();

  const importEditor = page.getByRole("dialog", { name: "E2E New Merchant" });
  await importEditor.getByLabel("Категория", { exact: true }).selectOption({ label: "Еда" });
  await importEditor.getByLabel("Запомнить для будущих импортов").check();
  const saveReview = page.waitForResponse((response) =>
    response.request().method() === "PATCH"
    && new URL(response.url()).pathname.includes("/preview/"),
  );
  await importEditor.getByRole("button", { name: "Сохранить изменения" }).click();
  const savedReviewResponse = await saveReview;
  expect(savedReviewResponse.status()).toBe(200);
  const savedReview = await savedReviewResponse.json() as {
    summary: { needs_review_count: number };
    rows: Array<{ status: string; proposed_category_name: string | null }>;
  };
  expect(savedReview.summary.needs_review_count).toBe(4);
  expect(savedReview.rows[0]?.status).toBe("auto_ready");
  expect(savedReview.rows[0]?.proposed_category_name).toBe("Еда");

  await page.getByRole("tab", { name: /Все/ }).click();
  const reviewedRow = importRow(page, "E2E New Merchant");
  await expect(reviewedRow.getByText("Готово", { exact: true })).toBeVisible();
  await expect(reviewedRow).toContainText("Категория: Еда");
  await page.getByLabel("Счёт для импорта").selectOption({ label: "E2E Main Card — UAH" });
  const confirmResponse = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && /\/imports\/[0-9a-f-]+\/confirm$/i.test(new URL(response.url()).pathname),
  );
  await page.getByRole("button", { name: "Подтвердить импорт" }).click();
  const confirmed = await confirmResponse;
  expect(confirmed.status()).toBe(200);
  const importResult = await confirmed.json() as {
    status: string;
    created_transactions: number;
    duplicate_count: number;
  };
  expect(importResult).toMatchObject({
    status: "confirmed",
    created_transactions: 6,
    duplicate_count: 1,
  });
  await expect(page.getByRole("heading", { name: "Импорт завершён" })).toBeVisible();
  const importResultPanel = page.getByRole("status");
  await expect(
    importResultPanel.locator(".confirm-metric").filter({ hasText: "Добавлено операций" }).locator("strong"),
  ).toHaveText("6");

  await page.getByRole("button", { name: "Перейти на дашборд" }).click();
  await expectDashboardAmount(page, "Доходы", /2[\s\u00a0\u202f]?000,00/);
  await expectDashboardAmount(page, "Расходы", /1[\s\u00a0\u202f]?350,00/);

  await page.getByRole("button", { name: "Операции" }).click();
  await expect(page.getByRole("heading", { name: "Операции" }).first()).toBeVisible();
  for (const importedName of [
    "E2E Market",
    "E2E Cafe",
    "E2E Payroll",
    "E2E Person Transfer",
    "E2E ATM Withdrawal",
    "E2E New Merchant",
  ]) {
    await expect(transactionRow(page, importedName)).toBeVisible();
  }
  await expect(transactionRow(page, "E2E Market")).toHaveCount(1);

  const manualExpenseResponse = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && new URL(response.url()).pathname.endsWith("/transactions"),
  );
  await createManualTransaction(page, {
    direction: "expense",
    amount: "250.00",
    description: "Кофе E2E",
    category: "Еда",
  });
  const manualExpense = await manualExpenseResponse;
  expect(manualExpense.status()).toBe(201);
  const expensePayload = await manualExpense.json() as { amount: string; direction: string };
  expect(expensePayload).toMatchObject({ amount: "-250.00", direction: "expense" });
  const coffeeExpense = transactionRow(page, "Кофе E2E");
  await expect(coffeeExpense.locator("b.amount-negative")).toContainText(/[-−]250,00/);
  await page.getByRole("button", { name: "Дашборд" }).click();
  await expectDashboardAmount(page, "Расходы", /1[\s\u00a0\u202f]?600,00/);

  await page.getByRole("button", { name: "Операции" }).click();
  const manualIncomeResponse = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && new URL(response.url()).pathname.endsWith("/transactions"),
  );
  await createManualTransaction(page, {
    direction: "income",
    amount: "1000.00",
    description: "E2E Income",
  });
  const manualIncome = await manualIncomeResponse;
  expect(manualIncome.status()).toBe(201);
  const incomePayload = await manualIncome.json() as { amount: string; direction: string };
  expect(incomePayload).toMatchObject({ amount: "1000.00", direction: "income" });
  await expect(transactionRow(page, "E2E Income").locator("b.amount-positive")).toContainText(/1[\s\u00a0\u202f]?000,00/);
  await page.getByRole("button", { name: "Дашборд" }).click();
  await expectDashboardAmount(page, "Доходы", /3[\s\u00a0\u202f]?000,00/);
  await expectDashboardAmount(page, "Расходы", /1[\s\u00a0\u202f]?600,00/);

  await page.getByRole("button", { name: "Операции" }).click();
  await transactionRow(page, "Кофе E2E").getByRole("button", { name: "Изменить" }).click();
  const transactionEditor = page.getByRole("dialog", { name: "Изменить" });
  await transactionEditor.getByLabel("Описание / место").fill("Кофе E2E исправлено");
  const updateResponse = page.waitForResponse((response) =>
    response.request().method() === "PATCH"
    && /\/transactions\/[0-9a-f-]+$/i.test(new URL(response.url()).pathname),
  );
  await transactionEditor.getByRole("button", { name: "Сохранить" }).click();
  const updated = await updateResponse;
  expect(updated.status()).toBe(200);
  const updatedPayload = await updated.json() as { display_description: string };
  expect(updatedPayload.display_description).toBe("Кофе E2E исправлено");

  await page.getByRole("button", { name: "Дашборд" }).click();
  await page.getByRole("button", { name: "Операции" }).click();
  await page.reload();
  await expect(transactionRow(page, "Кофе E2E исправлено")).toBeVisible();

  page.once("dialog", async (dialog) => {
    expect(dialog.message()).toContain("Удалить эту операцию?");
    await dialog.accept();
  });
  const deleteResponse = page.waitForResponse((response) =>
    response.request().method() === "DELETE"
    && /\/transactions\/[0-9a-f-]+$/i.test(new URL(response.url()).pathname),
  );
  // Trigger the native confirmation after registering its handler.
  await transactionRow(page, "Кофе E2E исправлено").getByRole("button", { name: "Удалить" }).click();
  expect((await deleteResponse).status()).toBe(204);
  await expect(transactionRow(page, "Кофе E2E исправлено")).toHaveCount(0);
  await page.reload();
  await expect(transactionRow(page, "Кофе E2E исправлено")).toHaveCount(0);
  await page.getByRole("button", { name: "Дашборд" }).click();
  await expectDashboardAmount(page, "Расходы", /1[\s\u00a0\u202f]?350,00/);

  await page.getByRole("button", { name: "Наличные" }).click();
  await expect(page.getByRole("heading", { name: "Создайте семейный кошелек наличных" })).toBeVisible();
  await page.getByRole("button", { name: "Создать кошелек" }).click();
  await expect(page.getByRole("heading", { name: "Снять наличные" })).toBeVisible();
  await expect(page.locator(".cash-balance strong")).toContainText(/0,00/);

  const withdrawalForm = page.locator("form").filter({
    has: page.getByRole("heading", { name: "Снять наличные" }),
  });
  await withdrawalForm.getByLabel("Сумма").fill("500.00");
  await withdrawalForm.getByLabel("Описание / место").fill("E2E cash withdrawal");
  const withdrawalResponse = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && new URL(response.url()).pathname.endsWith("/cash/transfers"),
  );
  await withdrawalForm.getByRole("button", { name: "Записать снятие" }).click();
  const withdrawal = await withdrawalResponse;
  expect(withdrawal.status()).toBe(201);
  expect(await withdrawal.json()).toMatchObject({ amount: "500.00", cash_balance: "500.00" });
  await expect(page.locator(".cash-balance strong")).toContainText(/500,00/);
  await page.getByRole("button", { name: "Дашборд" }).click();
  await expectDashboardAmount(page, "Расходы", /1[\s\u00a0\u202f]?350,00/);

  await page.getByRole("button", { name: "Наличные" }).click();
  const cashExpenseForm = page.locator("form").filter({
    has: page.getByRole("heading", { name: "Расход наличными" }),
  });
  await cashExpenseForm.getByLabel("Сумма").fill("120.00");
  await cashExpenseForm.getByLabel("Описание / место").fill("E2E cash expense");
  await cashExpenseForm.getByLabel("Категория", { exact: true }).selectOption({ label: "Еда" });
  const cashExpenseResponse = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && new URL(response.url()).pathname.endsWith("/cash/expenses"),
  );
  await cashExpenseForm.getByRole("button", { name: "Записать расход" }).click();
  const cashExpense = await cashExpenseResponse;
  expect(cashExpense.status()).toBe(201);
  expect(await cashExpense.json()).toMatchObject({ amount: "-120.00", flow_type: "cash_expense" });
  await expect(page.locator(".cash-balance strong")).toContainText(/380,00/);
  await page.getByRole("button", { name: "Дашборд" }).click();
  await expectDashboardAmount(page, "Расходы", /1[\s\u00a0\u202f]?470,00/);

  await page.getByLabel("Язык").selectOption("uk");
  await expect(page.getByRole("button", { name: "Операції" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Готівка" })).toBeVisible();
  await page.getByLabel("Мова").selectOption("ru");
  await expect(page.getByRole("button", { name: "Наличные" })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Наличные" }).click();
  await expect(page.getByRole("heading", { name: "Наличные", level: 1 })).toBeVisible();
  const mobileDocumentFits = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth,
  );
  expect(mobileDocumentFits).toBe(true);
});

function summaryMetric(summary: Locator, label: string) {
  return summary.locator(".import-metric").filter({ hasText: label }).locator("strong");
}

function importRow(page: Page, name: string) {
  return page.locator(".import-row-card").filter({
    has: page.getByRole("heading", { name, exact: true }),
  });
}

function transactionRow(page: Page, description: string) {
  return page.locator("article.full-transaction-row").filter({ hasText: description });
}

async function expectDashboardAmount(page: Page, label: string, value: RegExp) {
  const amount = page.locator(".kpi-card").filter({ hasText: label }).locator("strong");
  await expect(amount).toHaveText(value);
}

async function createManualTransaction(
  page: Page,
  values: { direction: "expense" | "income"; amount: string; description: string; category?: string },
) {
  await page.getByRole("button", { name: "Добавить операцию" }).click();
  const editor = page.getByRole("dialog", { name: "Добавить операцию" });
  await editor.getByLabel("Тип операции").selectOption(values.direction);
  await editor.getByLabel("Сумма").fill(values.amount);
  await editor.getByLabel("Счёт").selectOption({ label: "E2E Main Card · UAH" });
  await editor.getByLabel("Описание / место").fill(values.description);
  if (values.category) {
    await editor.getByLabel("Категория", { exact: true }).selectOption({ label: values.category });
  }
  await editor.getByRole("button", { name: "Сохранить" }).click();
  await expect(editor).toBeHidden();
}

function safePath(url: string) {
  return new URL(url).pathname.replace(/[0-9a-f-]{36}/gi, ":id");
}
