export type CurrentUser = {
  id: string;
  display_name: string;
  email: string;
  language: "ru" | "uk";
  family_id: string;
  family_name: string;
};

export type TelegramLinkStatus = {
  is_linked: boolean;
  username: string | null;
  first_name: string | null;
  linked_at: string | null;
};

export type TelegramLinkToken = {
  token: string;
  expires_at: string;
  telegram_url: string | null;
};

export type CategoryApiSubcategory = {
  id: string;
  category_id: string;
  name: string;
  translation_key: string | null;
  is_system: boolean;
};

export type CategoryApiRow = {
  id: string;
  family_id: string | null;
  name: string;
  translation_key: string | null;
  is_system: boolean;
  subcategories: CategoryApiSubcategory[];
};

export type CategoryListResponse = { rows: CategoryApiRow[] };

export type Account = {
  id: string;
  name: string;
  type: string;
  currency: string;
  is_active: boolean;
  owner_user_id: string | null;
  is_default: boolean;
};

export type AccountListResponse = { rows: Account[] };

export type TransactionDirection = "expense" | "income" | "transfer";
export type TransactionScope = "family" | "personal_main_user" | "work_fop";

export type TransactionRow = {
  id: string;
  account_id: string;
  account_name: string;
  occurred_at: string;
  amount: string;
  currency: string;
  direction: TransactionDirection;
  flow_type: string;
  income_type: string | null;
  scope: TransactionScope;
  description_raw: string | null;
  description_override: string | null;
  display_description: string | null;
  merchant_name: string | null;
  category_id: string | null;
  category_name: string | null;
  subcategory_id: string | null;
  subcategory_name: string | null;
  comment: string | null;
  needs_review: boolean;
};

export type TransactionListResponse = {
  total: number;
  offset: number;
  limit: number;
  rows: TransactionRow[];
};

export type ManualTransactionRequest = {
  direction: "expense" | "income";
  amount: string;
  account_id: string;
  occurred_at: string;
  merchant_name?: string | null;
  category_id?: string | null;
  subcategory_id?: string | null;
  flow_type?: string;
  income_type?: string;
  scope: TransactionScope;
  comment?: string | null;
};

export type TransactionUpdateRequest = Partial<ManualTransactionRequest>;

export type TransactionFilters = {
  date_from?: string;
  date_to?: string;
  account_id?: string;
  category_id?: string;
  uncategorized?: boolean;
  direction?: "expense" | "income";
  scope?: TransactionScope;
  needs_review?: boolean;
  offset?: number;
  limit?: number;
};

export function buildTransactionListUrl(href: string | URL, filters: TransactionFilters): URL {
  const url = new URL(href);
  if (filters.date_from) {
    url.searchParams.set("occurred_from", localDateBoundary(filters.date_from, false));
  }
  if (filters.date_to) {
    url.searchParams.set("occurred_to", localDateBoundary(filters.date_to, true));
  }
  for (const key of ["account_id", "category_id", "direction", "scope"] as const) {
    const value = filters[key];
    if (value) url.searchParams.set(key, value);
  }
  for (const key of ["uncategorized", "needs_review", "offset", "limit"] as const) {
    const value = filters[key];
    if (value !== undefined) url.searchParams.set(key, String(value));
  }
  return url;
}

export type ImportRowStatus =
  | "auto_ready"
  | "needs_review"
  | "duplicate_candidate"
  | "excluded"
  | "error";

export type ImportSummary = {
  import_batch_id: string;
  source_filename: string;
  status: string;
  period_start: string | null;
  period_end: string | null;
  total_rows: number;
  matching_rows_count: number;
  returned_rows: number;
  offset: number;
  limit: number;
  auto_ready_count: number;
  needs_review_count: number;
  imported_count: number;
  excluded_count: number;
  duplicate_count: number;
  error_count: number;
  uncategorized_count: number;
  work_fop_count: number;
  savings_count: number;
  parser_version: string;
  mapping_version: string;
  expires_at: string | null;
};

export type MatchedDuplicate = {
  transaction_id: string;
  occurred_at: string;
  amount: string;
  currency: string;
  description: string | null;
  merchant_name: string | null;
  category_name: string | null;
  import_batch_id: string | null;
};

export type ImportPreviewRow = {
  id: string;
  row_number: number;
  status: ImportRowStatus;
  reason_codes: string[];
  occurred_at: string | null;
  amount: string | null;
  currency: string | null;
  transaction_amount: string | null;
  transaction_currency: string | null;
  balance_after: string | null;
  payment_instrument_label: string | null;
  bank_category_raw: string | null;
  description_raw: string | null;
  merchant_name: string | null;
  proposed_category_id: string | null;
  proposed_category_name: string | null;
  proposed_subcategory_id: string | null;
  proposed_subcategory_name: string | null;
  proposed_flow_type: string | null;
  proposed_scope: string | null;
  confidence: string | null;
  duplicate_transaction_id: string | null;
  duplicate_of_row_number: number | null;
  duplicate_included: boolean;
  reviewed_uncategorized: boolean;
  reviewed_at: string | null;
  matched_duplicate: MatchedDuplicate | null;
  error_message: string | null;
  normalized_payload: Record<string, unknown>;
};

export type ImportPreviewResponse = {
  summary: ImportSummary;
  rows: ImportPreviewRow[];
};

export type ImportPreviewFilters = {
  offset?: number;
  limit?: number;
  row_status?: ImportRowStatus;
  reason_code?: string;
  merchant?: string;
  bank_category?: string;
  proposed_category_id?: string;
  uncategorized_only?: boolean;
};

export type ImportPreviewRowPatch = {
  proposed_category_id?: string | null;
  proposed_subcategory_id?: string | null;
  proposed_flow_type?: ImportFlowType | null;
  proposed_scope?: ImportScope | null;
  merchant_name?: string | null;
  excluded?: boolean;
  include_duplicate?: boolean;
  accept_uncategorized?: boolean;
  save_rule?: boolean;
  apply_to_merchant?: boolean;
};

export type ImportFlowType =
  | "purchase"
  | "cash_withdrawal"
  | "cash_expense"
  | "transfer_to_own_account"
  | "transfer_to_savings"
  | "transfer_to_wife"
  | "person_transfer"
  | "requisites_payment"
  | "refund"
  | "income"
  | "subscription"
  | "work_fop"
  | "other";

export type ImportScope = "family" | "personal_main_user" | "work_fop";

export type ImportBulkAction =
  | "assign_category"
  | "set_scope"
  | "set_flow_type"
  | "exclude"
  | "include_duplicate"
  | "mark_uncategorized"
  | "apply_correction";

export type ImportBulkActionRequest = ImportPreviewRowPatch & {
  action: ImportBulkAction;
  row_ids: string[];
};

export type ImportReviewSummary = {
  import_batch_id: string;
  status: string;
  total_rows: number;
  auto_ready_count: number;
  needs_review_count: number;
  imported_count: number;
  excluded_count: number;
  duplicate_count: number;
  error_count: number;
  uncategorized_count: number;
  work_fop_count: number;
  savings_count: number;
};

export type ImportReviewActionResponse = {
  requested_count: number;
  matched_count: number;
  changed_count: number;
  summary: ImportReviewSummary;
  rows: ImportPreviewRow[];
};

export type ConfirmImportResponse = {
  import_batch_id: string;
  status: string;
  created_transactions: number;
  excluded_count: number;
  duplicate_count: number;
  error_count: number;
  uncategorized_count: number;
  work_fop_count: number;
  savings_count: number;
};

type AccessTokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
let accessToken: string | null = null;
let refreshInFlight: Promise<string | null> | null = null;

export class AuthenticationRequiredError extends Error {
  constructor() {
    super("Your session has expired. Please sign in again.");
    this.name = "AuthenticationRequiredError";
  }
}

export function apiUrl(path: string): URL {
  return new URL(path.replace(/^\//, ""), `${API_BASE_URL.replace(/\/$/, "")}/`);
}

export async function signIn(email: string, password: string): Promise<void> {
  const response = await fetch(apiUrl("/auth/login"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw new Error(await responseError(response, "Sign in failed."));
  }
  const tokens = (await response.json()) as AccessTokenResponse;
  accessToken = tokens.access_token;
}

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) {
    return refreshInFlight;
  }
  refreshInFlight = (async () => {
    try {
      const response = await fetch(apiUrl("/auth/refresh"), {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        accessToken = null;
        return null;
      }
      const tokens = (await response.json()) as AccessTokenResponse;
      accessToken = tokens.access_token;
      return accessToken;
    } catch {
      accessToken = null;
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

export async function signOut(): Promise<void> {
  try {
    await fetch(apiUrl("/auth/logout"), {
      method: "POST",
      credentials: "include",
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
    });
  } finally {
    accessToken = null;
  }
}

export function clearAccessToken(): void {
  accessToken = null;
}

export async function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  if (!accessToken) {
    throw new AuthenticationRequiredError();
  }

  const send = () => {
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${accessToken}`);
    return fetch(input, { ...init, headers, credentials: "include" });
  };

  let response = await send();
  if (response.status === 401) {
    if (!(await refreshAccessToken())) {
      throw new AuthenticationRequiredError();
    }
    response = await send();
  }
  return response;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  const response = await authenticatedFetch(apiUrl("/auth/me"));
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not load your account."));
  }
  return (await response.json()) as CurrentUser;
}

export async function getTelegramLinkStatus(): Promise<TelegramLinkStatus> {
  const response = await authenticatedFetch(apiUrl("/telegram/link-status"));
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not load Telegram link status."));
  }
  return (await response.json()) as TelegramLinkStatus;
}

export async function createTelegramLink(): Promise<TelegramLinkToken> {
  const response = await authenticatedFetch(apiUrl("/telegram/link-token"), { method: "POST" });
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not create a Telegram link."));
  }
  return (await response.json()) as TelegramLinkToken;
}

export async function deleteTelegramLink(): Promise<void> {
  const response = await authenticatedFetch(apiUrl("/telegram/link"), { method: "DELETE" });
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not unlink Telegram."));
  }
}

export async function getCategories(): Promise<CategoryListResponse> {
  const response = await authenticatedFetch(apiUrl("/categories"));
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not load categories."));
  }
  return (await response.json()) as CategoryListResponse;
}

export async function getAccounts(): Promise<AccountListResponse> {
  const response = await authenticatedFetch(apiUrl("/accounts"));
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not load accounts."));
  }
  return (await response.json()) as AccountListResponse;
}

export async function listTransactions(
  filters: TransactionFilters = {},
): Promise<TransactionListResponse> {
  const response = await authenticatedFetch(buildTransactionListUrl(apiUrl("/transactions"), filters));
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not load transactions."));
  }
  return (await response.json()) as TransactionListResponse;
}

export async function createTransaction(
  payload: ManualTransactionRequest,
): Promise<TransactionRow> {
  const response = await authenticatedFetch(apiUrl("/transactions"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not create this transaction."));
  }
  return (await response.json()) as TransactionRow;
}

export async function updateTransaction(
  transactionId: string,
  payload: TransactionUpdateRequest,
): Promise<TransactionRow> {
  const response = await authenticatedFetch(
    apiUrl(`/transactions/${encodeURIComponent(transactionId)}`),
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not update this transaction."));
  }
  return (await response.json()) as TransactionRow;
}

export async function deleteTransaction(transactionId: string): Promise<void> {
  const response = await authenticatedFetch(
    apiUrl(`/transactions/${encodeURIComponent(transactionId)}`),
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not delete this transaction."));
  }
}

function localDateBoundary(value: string, endOfDay: boolean): string {
  const date = new Date(`${value}T${endOfDay ? "23:59:59.999" : "00:00:00"}`);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString();
}

export async function uploadImportPreview(file: File, limit = 50): Promise<ImportPreviewResponse> {
  const form = new FormData();
  form.append("file", file);
  const url = apiUrl("/imports/preview");
  url.searchParams.set("preview_limit", String(limit));
  const response = await authenticatedFetch(url, { method: "POST", body: form });
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not upload this statement."));
  }
  return (await response.json()) as ImportPreviewResponse;
}

export async function getImportPreview(
  importBatchId: string,
  filters: ImportPreviewFilters = {},
): Promise<ImportPreviewResponse> {
  const url = apiUrl(`/imports/${encodeURIComponent(importBatchId)}/preview`);
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "" && value !== false) {
      url.searchParams.set(key, String(value));
    } else if (value === false && key === "uncategorized_only") {
      url.searchParams.set(key, "false");
    }
  }
  const response = await authenticatedFetch(url);
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not load the import preview."));
  }
  return (await response.json()) as ImportPreviewResponse;
}

export async function patchImportPreviewRow(
  importBatchId: string,
  rowId: string,
  payload: ImportPreviewRowPatch,
): Promise<ImportReviewActionResponse> {
  const response = await authenticatedFetch(
    apiUrl(`/imports/${encodeURIComponent(importBatchId)}/preview/${encodeURIComponent(rowId)}`),
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not save this row."));
  }
  return (await response.json()) as ImportReviewActionResponse;
}

export async function executeImportBulkAction(
  importBatchId: string,
  payload: ImportBulkActionRequest,
): Promise<ImportReviewActionResponse> {
  const response = await authenticatedFetch(
    apiUrl(`/imports/${encodeURIComponent(importBatchId)}/bulk-actions`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not apply this bulk action."));
  }
  return (await response.json()) as ImportReviewActionResponse;
}

export async function confirmImport(
  importBatchId: string,
  accountId: string,
): Promise<ConfirmImportResponse> {
  const url = apiUrl(`/imports/${encodeURIComponent(importBatchId)}/confirm`);
  url.searchParams.set("account_id", accountId);
  const response = await authenticatedFetch(url, { method: "POST" });
  if (!response.ok) {
    throw new Error(await responseError(response, "Could not confirm this import."));
  }
  return (await response.json()) as ConfirmImportResponse;
}

async function responseError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Keep the user facing fallback when the response has no JSON body.
  }
  return `${response.status}: ${fallback}`;
}
