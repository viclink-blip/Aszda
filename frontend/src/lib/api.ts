/**
 * Typed client for the ASZDA API.
 *
 * - All requests go to /api/* on this same site; next.config.ts forwards them to Flask.
 * - The access token lives only in this module's memory (never localStorage).
 *   The AuthProvider (lib/auth.tsx) is the only code that sets it.
 * - When a request fails with an expired token, we refresh once (sharing one
 *   refresh between concurrent requests) and retry the request once.
 */

import type {
  AdminJob,
  AdminPricing,
  GenerationPriceInput,
  AdminPayment,
  BillingCatalog,
  BillingOverview,
  CheckoutStatus,
  CurrencyInfo,
  Payment,
  PaymentStatus,
  SubscriptionInfo,
  AdminOverview,
  AdminUser,
  Asset,
  AssetKind,
  AuditEvent,
  Character,
  CreditAccount,
  CreditTransaction,
  Dashboard,
  GenerationKind,
  Job,
  JobStatus,
  Page,
  Project,
  ProjectDetail,
  ProjectStatus,
  Provider,
  Quote,
  Role,
  Scene,
  SessionResponse,
  UsageReport,
  User,
} from "./types";

// ---- Errors -------------------------------------------------------------------

export interface FieldError {
  field: string;
  message: string;
}

/** Every failed request becomes an ApiError with the server's code and message. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details ?? {};
  }

  /** Validation errors (422) as { fieldName: message }. Nested names keep their last part. */
  get fieldErrors(): Record<string, string> {
    const fields = this.details.fields;
    if (!Array.isArray(fields)) return {};
    const out: Record<string, string> = {};
    for (const item of fields as FieldError[]) {
      const name = String(item.field).split(".").pop() || "form";
      // Pydantic prefixes some messages with "Value error, "; drop it for readers.
      out[name] = out[name] ?? item.message.replace(/^Value error, /, "");
    }
    return out;
  }

  /** Password problems from a `weak_password` error. */
  get problems(): string[] {
    const problems = this.details.problems;
    return Array.isArray(problems) ? problems.map(String) : [];
  }

  get isNetworkError(): boolean {
    return this.status === 0;
  }
}

/** A readable message for any thrown value. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const fields = Object.values(error.fieldErrors);
    if (error.code === "validation_error" && fields.length > 0) return fields.join(" ");
    if (error.problems.length > 0) return `${error.message} ${error.problems.join(" ")}`;
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

// ---- Token handling -------------------------------------------------------------

let accessToken: string | null = null;
let refreshInFlight: Promise<SessionResponse | null> | null = null;
let onSessionChange: (session: SessionResponse | null) => void = () => {};

/** Called by AuthProvider only. */
export function setAccessToken(token: string | null): void {
  accessToken = token;
}

/** AuthProvider registers here so a background refresh (or its failure) updates the UI. */
export function setSessionListener(listener: (session: SessionResponse | null) => void): void {
  onSessionChange = listener;
}

// Header the API requires on cookie-authenticated endpoints (CSRF protection).
const CSRF_HEADERS = { "X-Requested-With": "aszda" };

/**
 * Swap the HttpOnly refresh cookie for a new access token.
 * Concurrent callers share one network request. Resolves null when signed out.
 */
export function refreshSession(): Promise<SessionResponse | null> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch("/api/auth/refresh", {
          method: "POST",
          headers: CSRF_HEADERS,
          credentials: "same-origin",
        });
        if (!response.ok) {
          accessToken = null;
          onSessionChange(null);
          return null;
        }
        const session = (await response.json()) as SessionResponse;
        accessToken = session.access_token;
        onSessionChange(session);
        return session;
      } catch {
        // Network problem: keep the current state; the caller decides what to show.
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

// ---- Core request -----------------------------------------------------------------

interface RequestOptions {
  body?: unknown;
  form?: FormData;
  query?: Record<string, string | number | undefined | null>;
  headers?: Record<string, string>;
  /** Send the access token (default true). */
  auth?: boolean;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const data = await response.json();
    const err = data?.error;
    if (err && typeof err.code === "string") {
      return new ApiError(response.status, err.code, err.message ?? "Request failed.", err.details);
    }
  } catch {
    // Not JSON (for example a proxy error page).
  }
  if (response.status >= 500) {
    return new ApiError(response.status, "server_error",
      "The ASZDA service is not responding properly. Please try again shortly.");
  }
  return new ApiError(response.status, "http_error", `Request failed (${response.status}).`);
}

async function send(method: string, path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { ...options.headers };
  let body: BodyInit | undefined;
  if (options.form) {
    body = options.form; // the browser sets the multipart boundary itself
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  if (options.auth !== false && accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  try {
    return await fetch(buildUrl(path, options.query), {
      method,
      headers,
      body,
      credentials: "same-origin",
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error",
      "Could not reach ASZDA. Check your connection and try again.");
  }
}

export async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(method, path, options);

  if (response.status === 401 && options.auth !== false) {
    const error = await parseError(response.clone());
    if (error.code === "token_expired" || error.code === "invalid_token") {
      const session = await refreshSession();
      if (!session) throw error;
      response = await send(method, path, options); // retry exactly once
    } else if (error.code === "session_revoked" || error.code === "account_inactive") {
      accessToken = null;
      onSessionChange(null);
    }
  }

  if (!response.ok) throw await parseError(response);
  if (response.status === 204 || response.status === 202) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

const get = <T>(path: string, query?: RequestOptions["query"]) => request<T>("GET", path, { query });
const post = <T>(path: string, body?: unknown, headers?: Record<string, string>) =>
  request<T>("POST", path, { body: body ?? {}, headers });
const patch = <T>(path: string, body: unknown) => request<T>("PATCH", path, { body });
const del = (path: string, body?: unknown) => request<void>("DELETE", path, { body });

// ---- Endpoints ----------------------------------------------------------------------

export interface ListQuery {
  limit?: number;
  offset?: number;
}

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<SessionResponse>("POST", "/api/auth/login", { body: { email, password }, auth: false }),
    register: (data: { email: string; password: string; display_name: string; accept_terms: boolean }) =>
      request<SessionResponse>("POST", "/api/auth/register", { body: data, auth: false }),
    logout: () => request<void>("POST", "/api/auth/logout", { headers: CSRF_HEADERS, auth: false }),
    logoutAll: () => post<void>("/api/auth/logout-all"),
    verifyEmail: (token: string) =>
      request<{ user: User }>("POST", "/api/auth/verify-email", { body: { token }, auth: false }),
    resendVerification: () => post<void>("/api/auth/resend-verification"),
    requestPasswordReset: (email: string) =>
      request<void>("POST", "/api/auth/password-reset/request", { body: { email }, auth: false }),
    confirmPasswordReset: (token: string, new_password: string) =>
      request<void>("POST", "/api/auth/password-reset/confirm", { body: { token, new_password }, auth: false }),
  },

  me: {
    get: () => get<{ user: User }>("/api/me"),
    update: (data: { display_name?: string; preferred_language?: string | null; country?: string | null }) =>
      patch<{ user: User }>("/api/me", data),
    changePassword: (current_password: string, new_password: string) =>
      post<void>("/api/me/password", { current_password, new_password }),
    deleteAccount: (password: string, confirm: string) => del("/api/me", { password, confirm }),
    dashboard: () => get<Dashboard>("/api/me/dashboard"),
    credits: (q: ListQuery = {}) =>
      get<{ account: CreditAccount; transactions: Page<CreditTransaction> }>("/api/me/credits", { ...q }),
  },

  projects: {
    list: (q: ListQuery & { status?: ProjectStatus | ""; q?: string } = {}) =>
      get<Page<Project>>("/api/projects", { ...q }),
    get: (id: string) => get<ProjectDetail>(`/api/projects/${id}`),
    create: (data: { title: string; description?: string }) =>
      post<{ project: Project }>("/api/projects", data),
    update: (id: string, data: { title?: string; description?: string; status?: ProjectStatus }) =>
      patch<{ project: Project }>(`/api/projects/${id}`, data),
    remove: (id: string) => del(`/api/projects/${id}`),
    duplicate: (id: string) => post<{ project: Project }>(`/api/projects/${id}/duplicate`),
    assets: (id: string, q: ListQuery & { kind?: AssetKind | "" } = {}) =>
      get<Page<Asset>>(`/api/projects/${id}/assets`, { ...q }),
    jobs: (id: string, q: ListQuery = {}) => get<Page<Job>>(`/api/projects/${id}/jobs`, { ...q }),
  },

  characters: {
    create: (projectId: string, data: CharacterInput) =>
      post<{ character: Character }>(`/api/projects/${projectId}/characters`, data),
    update: (projectId: string, id: string, data: Partial<CharacterInput>) =>
      patch<{ character: Character }>(`/api/projects/${projectId}/characters/${id}`, data),
    remove: (projectId: string, id: string) => del(`/api/projects/${projectId}/characters/${id}`),
  },

  scenes: {
    create: (projectId: string, data: SceneInput) =>
      post<{ scene: Scene }>(`/api/projects/${projectId}/scenes`, data),
    update: (projectId: string, id: string, data: Partial<SceneInput>) =>
      patch<{ scene: Scene }>(`/api/projects/${projectId}/scenes/${id}`, data),
    remove: (projectId: string, id: string) => del(`/api/projects/${projectId}/scenes/${id}`),
    reorder: (projectId: string, sceneIds: string[]) =>
      request<{ scenes: Scene[] }>("PUT", `/api/projects/${projectId}/scenes/order`, {
        body: { scene_ids: sceneIds },
      }),
  },

  assets: {
    list: (q: ListQuery & { kind?: AssetKind | "" } = {}) => get<Page<Asset>>("/api/assets", { ...q }),
    get: (id: string) => get<{ asset: Asset }>(`/api/assets/${id}`),
    /** Upload into a project, or into the personal library when projectId is null. */
    upload: (file: File, projectId: string | null) => {
      const form = new FormData();
      form.append("file", file);
      const path = projectId ? `/api/projects/${projectId}/assets` : "/api/assets";
      return request<{ asset: Asset }>("POST", path, { form });
    },
    rename: (id: string, display_name: string) => patch<{ asset: Asset }>(`/api/assets/${id}`, { display_name }),
    remove: (id: string) => del(`/api/assets/${id}`),
    /** A short-lived link to the file. Fetch a fresh one each time you display it. */
    url: (id: string) => get<{ url: string; expires_in: number }>(`/api/assets/${id}/url`),
  },

  generation: {
    providers: () => get<{ providers: Provider[] }>("/api/providers"),
    quote: (data: GenerationInput) =>
      post<Quote>("/api/generation-jobs/quote", {
        provider: data.provider, model: data.model, kind: data.kind, params: data.params,
      }),
    create: (data: GenerationInput, idempotencyKey: string) =>
      post<{ job: Job }>("/api/generation-jobs", data, { "Idempotency-Key": idempotencyKey }),
    list: (q: ListQuery & { status?: JobStatus | ""; kind?: GenerationKind | ""; project_id?: string } = {}) =>
      get<Page<Job>>("/api/generation-jobs", { ...q }),
    get: (id: string) => get<{ job: Job }>(`/api/generation-jobs/${id}`),
    cancel: (id: string) => post<{ job: Job }>(`/api/generation-jobs/${id}/cancel`),
    retry: (id: string, idempotencyKey: string) =>
      post<{ job: Job }>(`/api/generation-jobs/${id}/retry`, {}, { "Idempotency-Key": idempotencyKey }),
  },

  billing: {
    /** Public: works signed out too (pricing page). */
    catalog: () => request<BillingCatalog>("GET", "/api/billing/catalog", { auth: false }),
    overview: () => get<BillingOverview>("/api/billing/overview"),
    /** Only WHAT to buy is sent; the server decides the price, currency and credits. */
    checkout: (item_type: "credit_package" | "subscription", item_code: string) =>
      post<{ payment: Payment; authorization_url: string }>("/api/billing/checkout", { item_type, item_code }),
    confirm: (reference: string) => post<{ payment: Payment }>("/api/billing/confirm", { reference }),
    payments: (q: ListQuery = {}) => get<Page<Payment>>("/api/billing/payments", { ...q }),
    payment: (id: string) =>
      get<{ payment: Payment; currency: CurrencyInfo; seller: { name: string; product: string } }>(
        `/api/billing/payments/${id}`),
    cancelSubscription: () => post<{ subscription: SubscriptionInfo }>("/api/billing/subscription/cancel"),
  },

  admin: {
    overview: () => get<AdminOverview>("/api/admin/overview"),
    pricing: () => get<AdminPricing>("/api/admin/pricing"),
    setGenerationPrice: (provider: string, model: string, data: GenerationPriceInput) =>
      request<AdminPricing>("PUT", `/api/admin/pricing/generation/${provider}/${model}`, { body: data }),
    clearGenerationPrice: (provider: string, model: string) =>
      request<AdminPricing>("DELETE", `/api/admin/pricing/generation/${provider}/${model}`),
    setBillingItem: (itemType: "plan" | "credit_package", code: string,
      data: { credits: number | null; paystack_plan_code?: string | null; monthly_credit_limit?: number | null }) =>
      request<AdminPricing>("PUT", `/api/admin/pricing/billing/${itemType}/${code}`, { body: data }),
    payments: (q: ListQuery & { status?: PaymentStatus | "" } = {}) =>
      get<Page<AdminPayment> & { checkout: CheckoutStatus }>("/api/admin/payments", { ...q }),
    users: (q: ListQuery & { q?: string } = {}) => get<Page<AdminUser>>("/api/admin/users", { ...q }),
    updateUser: (id: string, data: { is_active?: boolean; role?: Role }) =>
      patch<{ user: AdminUser }>(`/api/admin/users/${id}`, data),
    adjustCredits: (id: string, amount: number, reason: string) =>
      post<{ transaction: CreditTransaction }>(`/api/admin/users/${id}/credits`, { amount, reason }),
    userCredits: (id: string, q: ListQuery = {}) =>
      get<{ balance: number; transactions: Page<CreditTransaction> }>(`/api/admin/users/${id}/credits`, { ...q }),
    jobs: (q: ListQuery & { status?: JobStatus | ""; provider?: string } = {}) =>
      get<Page<AdminJob>>("/api/admin/jobs", { ...q }),
    usage: (days: number) => get<UsageReport>("/api/admin/usage", { days }),
    providers: () => get<{ providers: Provider[] }>("/api/admin/providers"),
    auditEvents: (q: ListQuery & { action?: string } = {}) =>
      get<Page<AuditEvent>>("/api/admin/audit-events", { ...q }),
  },
};

export interface CharacterInput {
  name: string;
  description?: string;
  traits?: Record<string, unknown>;
  reference_asset_id?: string | null;
}

export interface SceneInput {
  title: string;
  description?: string;
  shot_notes?: string;
  dialogue?: string;
  duration_seconds?: number | null;
  character_ids?: string[];
  preview_asset_id?: string | null;
}

export interface GenerationInput {
  provider: string;
  model: string;
  kind: GenerationKind;
  params: Record<string, unknown>;
  project_id?: string | null;
  scene_id?: string | null;
}

/** A new random Idempotency-Key for one submit attempt. */
export function newIdempotencyKey(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  // randomUUID needs a secure context (HTTPS or localhost); fall back to random bytes.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
