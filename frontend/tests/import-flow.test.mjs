import assert from "node:assert/strict";
import { test } from "node:test";

import {
  apiUrl,
  clearAccessToken,
  confirmImport,
  refreshAccessToken,
  signIn,
  uploadImportPreview,
} from "../src/api.ts";
import {
  buildBulkActionRequest,
  buildImportRowPatch,
  categorySelectionChanged,
  correctedPageOffset,
  filterSelectedRows,
  recommendedImportTab,
} from "../src/import/logic.ts";

const uuid = "11111111-1111-4111-8111-111111111111";

function tokenResponse(token = "access-token") {
  return new Response(JSON.stringify({ access_token: token, token_type: "bearer", expires_in: 900 }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function summary(overrides = {}) {
  return {
    error_count: 0,
    needs_review_count: 0,
    duplicate_count: 0,
    ...overrides,
  };
}

test("upload calls the authenticated preview endpoint with the selected XLSX", async () => {
  clearAccessToken();
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (input, init = {}) => {
    calls.push({ url: String(input), init });
    if (String(input).endsWith("/auth/login")) return tokenResponse();
    return new Response(JSON.stringify({ summary: { import_batch_id: uuid }, rows: [] }), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    });
  };
  try {
    await signIn("demo@example.com", "synthetic-password");
    const file = new File(["synthetic xlsx bytes"], "synthetic-statement.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const result = await uploadImportPreview(file, 50);

    const request = calls[1];
    assert.match(request.url, /\/imports\/preview\?preview_limit=50$/);
    assert.equal(request.init.method, "POST");
    assert.equal(new Headers(request.init.headers).get("Authorization"), "Bearer access-token");
    assert.equal(request.init.body.get("file").name, "synthetic-statement.xlsx");
    assert.equal(result.summary.import_batch_id, uuid);
  } finally {
    globalThis.fetch = originalFetch;
    clearAccessToken();
  }
});

test("default filter prioritizes errors, then review, then duplicates", () => {
  assert.equal(recommendedImportTab(summary({ error_count: 2, needs_review_count: 5 })), "errors");
  assert.equal(recommendedImportTab(summary({ needs_review_count: 5, duplicate_count: 4 })), "needs_review");
  assert.equal(recommendedImportTab(summary({ duplicate_count: 4 })), "duplicates");
  assert.equal(recommendedImportTab(summary()), "all");
});

test("page offset moves back when a row edit removes the last page", () => {
  assert.equal(correctedPageOffset(100, 50, 73), 50);
  assert.equal(correctedPageOffset(50, 50, 50), 0);
  assert.equal(correctedPageOffset(0, 50, 0), 0);
});

test("changing category clears a previous subcategory", () => {
  assert.deepEqual(categorySelectionChanged("category-b"), {
    categoryId: "category-b",
    subcategoryId: "",
    intentionalUncategorized: false,
  });
});

test("intentional uncategorized is sent as a distinct review decision", () => {
  const payload = buildImportRowPatch({
    merchantName: "Corner Shop",
    categoryId: "",
    subcategoryId: "",
    flowType: "purchase",
    scope: "family",
    excluded: false,
    includeDuplicate: false,
    hasDuplicate: false,
    intentionalUncategorized: true,
    saveRule: false,
    applyToMerchant: false,
  });
  assert.equal(payload.proposed_category_id, null);
  assert.equal(payload.proposed_subcategory_id, null);
  assert.equal(payload.accept_uncategorized, true);
});

test("duplicate inclusion sends the backend duplicate decision", () => {
  const payload = buildImportRowPatch({
    merchantName: "Corner Shop",
    categoryId: "category-a",
    subcategoryId: "subcategory-a",
    flowType: "purchase",
    scope: "family",
    excluded: false,
    includeDuplicate: true,
    hasDuplicate: true,
    intentionalUncategorized: false,
    saveRule: false,
    applyToMerchant: false,
  });
  assert.equal(payload.include_duplicate, true);
});

test("bulk payload uses only the explicitly selected visible row IDs", () => {
  const rows = [
    { id: "row-1", row_number: 2 },
    { id: "row-2", row_number: 3 },
    { id: "row-not-selected", row_number: 4 },
  ];
  const selected = filterSelectedRows(rows, new Set(["row-1", "row-2"]));
  const payload = buildBulkActionRequest("exclude", selected, { save_rule: false, apply_to_merchant: false });
  assert.deepEqual(payload.row_ids, ["row-1", "row-2"]);
  assert.equal("all_matching" in payload, false);
});

test("confirmation sends the selected account ID in the query", async () => {
  clearAccessToken();
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (input, init = {}) => {
    calls.push({ url: String(input), init });
    if (String(input).endsWith("/auth/login")) return tokenResponse();
    return new Response(JSON.stringify({ import_batch_id: uuid, status: "confirmed", created_transactions: 1 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  try {
    await signIn("demo@example.com", "synthetic-password");
    await confirmImport(uuid, "22222222-2222-4222-8222-222222222222");
    const requestUrl = new URL(calls[1].url);
    assert.equal(requestUrl.pathname, `/api/v1/imports/${uuid}/confirm`);
    assert.equal(requestUrl.searchParams.get("account_id"), "22222222-2222-4222-8222-222222222222");
    assert.equal(calls[1].init.method, "POST");
  } finally {
    globalThis.fetch = originalFetch;
    clearAccessToken();
  }
});

test("expired authentication uses the existing refresh path and rejects safely", async () => {
  clearAccessToken();
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (input) => {
    const url = String(input);
    calls.push(url);
    if (url.endsWith("/auth/login")) return tokenResponse();
    if (url.endsWith("/auth/refresh")) return new Response("", { status: 401 });
    return new Response("", { status: 401 });
  };
  try {
    await signIn("demo@example.com", "synthetic-password");
    const error = await refreshAccessToken().then(() => null, (reason) => reason);
    assert.equal(error, null);
    await assert.rejects(
      async () => {
        clearAccessToken();
        await signIn("demo@example.com", "synthetic-password");
        await (await import("../src/api.ts")).authenticatedFetch(apiUrl("/transactions"));
      },
      (reason) => reason?.name === "AuthenticationRequiredError",
    );
    assert.ok(calls.some((url) => url.endsWith("/auth/refresh")));
  } finally {
    globalThis.fetch = originalFetch;
    clearAccessToken();
  }
});
