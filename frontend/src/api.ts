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

type AccessTokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
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
