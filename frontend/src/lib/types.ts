/**
 * TypeScript shapes of what the ASZDA API returns.
 * These mirror backend/app/schemas/serializers.py — keep them in sync.
 */

export type Role = "user" | "admin";

export interface User {
  id: string;
  email: string;
  display_name: string;
  preferred_language: string | null;
  country: string | null;
  role: Role;
  email_verified: boolean;
  created_at: string | null;
}

/** Admin views include a few extra fields. */
export interface AdminUser extends User {
  is_active: boolean;
  last_login_at: string | null;
  credit_balance: number;
}

export interface SessionResponse {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
  user: User;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export type ProjectStatus = "draft" | "in_progress" | "completed" | "archived";

export interface Project {
  id: string;
  title: string;
  description: string;
  status: ProjectStatus;
  brief: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  // Present on list/detail responses (project_stats); absent right after create/update.
  character_count?: number;
  scene_count?: number;
  asset_count?: number;
}

export interface Character {
  id: string;
  project_id: string;
  name: string;
  description: string;
  traits: Record<string, unknown>;
  reference_asset_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface Scene {
  id: string;
  project_id: string;
  position: number;
  title: string;
  description: string;
  shot_notes: string;
  dialogue: string;
  duration_seconds: number | null;
  character_ids: string[];
  preview_asset_id: string | null;
  /** Prompts written by the AI Film Director (empty for hand-made scenes). */
  ai_prompts: { image_prompt?: string; video_prompt?: string; narration?: string; style?: string; plan_job_id?: string };
  created_at: string | null;
  updated_at: string | null;
}

export interface ProjectDetail {
  project: Project;
  characters: Character[];
  scenes: Scene[];
}

export type AssetKind = "image" | "video" | "audio" | "text";

export interface Asset {
  id: string;
  project_id: string | null;
  generation_job_id: string | null;
  kind: AssetKind;
  source: "upload" | "generated";
  display_name: string;
  original_filename: string | null;
  mime_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  /** For generated assets: the AI provider and model that produced it. */
  provider?: string | null;
  model?: string | null;
  created_at: string | null;
}

export type JobStatus = "queued" | "validating" | "processing" | "completed" | "failed" | "cancelled";
export type GenerationKind = "text" | "image" | "video" | "animation" | "speech";

export interface JobResult {
  asset_ids?: string[];
  text?: string;
  title?: string;
  truncated?: boolean;
  [key: string]: unknown;
}

export interface Job {
  id: string;
  project_id: string | null;
  scene_id: string | null;
  retry_of_id: string | null;
  kind: GenerationKind;
  provider: string;
  model: string;
  params: Record<string, unknown>;
  status: JobStatus;
  progress: number | null;
  result: JobResult | null;
  error: { code: string; message: string } | null;
  credits_reserved: number;
  credits_charged: number | null;
  attempts: number;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface AdminJob extends Job {
  user_id: string;
  usage: Record<string, unknown> | null;
  provider_job_id: string | null;
}

export const ACTIVE_JOB_STATUSES: JobStatus[] = ["queued", "validating", "processing"];

export function isJobActive(status: JobStatus): boolean {
  return ACTIVE_JOB_STATUSES.includes(status);
}

export interface CreditAccount {
  balance: number;
  /** Subscription credits: expire at plan_credits_expire_at and do not roll over. Spent first. */
  plan_balance: number;
  plan_credits_expire_at: string | null;
  /** Credit packages, the sign-up grant and admin grants: never expire. */
  purchased_balance: number;
  updated_at: string | null;
}

export type CreditTxType =
  | "grant" | "purchase" | "plan_allowance" | "expire" | "reserve" | "release" | "refund" | "adjustment";

export interface CreditTransaction {
  id: string;
  type: CreditTxType;
  amount: number;
  plan_amount: number;
  purchased_amount: number;
  balance_after: number;
  generation_job_id: string | null;
  reason: string | null;
  created_at: string | null;
}

export interface Dashboard {
  user: User;
  credits: CreditAccount;
  counts: { projects: number; assets: number; active_jobs: number };
  recent_projects: Project[];
  recent_jobs: Job[];
  recent_assets: Asset[];
}

// ---- Providers (GET /api/providers) -------------------------------------------

export type SettingFieldType = "text" | "textarea" | "select" | "integer" | "number" | "boolean" | "asset";

/** One setting a model accepts; mirrors SettingField in backend/app/providers/base.py. */
export interface SettingField {
  name: string;
  label: string;
  type: SettingFieldType;
  required: boolean;
  help: string | null;
  options: { value: string; label: string }[] | null;
  minimum: number | null;
  maximum: number | null;
  max_length: number | null;
  default: unknown;
  asset_kind: AssetKind | null;
  show_when: Record<string, string[]> | null;
}

export type UnavailableReason =
  | "provider_not_configured" | "pricing_not_configured" | "provider_disabled" | "model_retired" | "unsupported_model";

export interface ProviderModel {
  id: string;
  label: string;
  kind: GenerationKind;
  description: string;
  fields: SettingField[];
  usage_metrics: string[];
  pricing: { credits_per_1000: Record<string, number>; minimum_credits: number } | null;
  deprecated: string | null;
  shutdown_on: string | null;
  is_default: boolean;
  available: boolean;
  unavailable_reason: UnavailableReason | null;
}

export interface Provider {
  name: string;
  label: string;
  configured: boolean;
  enabled: boolean;
  capabilities: GenerationKind[];
  supports_cancel: boolean;
  models: ProviderModel[];
  credential_env?: string; // admin endpoint only
}

export interface Quote {
  priced: boolean;
  estimated_credits: number | null;
  estimated_usage: Record<string, number>;
  balance: number;
  provider: string;
  model: string;
  fallback_used: boolean;
}

// ---- AI routing, provider health and costs -----------------------------------------

export interface CapabilityRoute {
  kind: "text" | "image" | "video" | "speech";
  preferred_provider: string | null;
  fallback_providers: string[];
  ready: { provider: string; model: string; fallback_used: boolean } | null;
  problem: { code: string; message: string; details: { tried?: { provider: string; reason: string; message: string }[] } } | null;
}

export interface ProviderHealth {
  name: string;
  label: string;
  credentials_configured: boolean;
  settings_complete: boolean;
  /** Names of missing environment variables. Values are never sent. */
  missing_settings: string[];
  enabled: boolean;
  capabilities: GenerationKind[];
  models: {
    id: string; kind: GenerationKind; is_default: boolean; priced: boolean; deprecated: string | null;
    shutdown_on: string | null; available: boolean; unavailable_reason: UnavailableReason | null;
  }[];
  connection_test: { available: boolean; description: string | null; may_charge: boolean };
  last_test: {
    tested_at: string | null; ok: boolean | null; result: string | null; last_success_at: string | null;
    last_error: string | null; last_error_at: string | null;
  } | null;
}

export interface ProviderCostRow {
  provider: string;
  model: string;
  outcome: "completed" | "safety_blocked" | "failed_billed";
  absorbed_by_aszda: boolean;
  jobs: number;
  estimated_usd: string | null;
  jobs_with_estimate: number;
  credits_charged: number;
}

export interface SceneGenerationResult {
  kind: "image" | "video" | "voice";
  job_id?: string;
  created?: boolean;
  provider?: string;
  model?: string;
  skipped?: string;
  error?: { code: string; message: string };
}

// ---- Admin --------------------------------------------------------------------

export interface AdminOverview {
  period_days: number;
  users: { total: number; new: number };
  projects: number;
  jobs: Record<JobStatus, number>;
  credits_charged: number;
  credits_outstanding: number;
}

export interface UsageRow {
  provider: string;
  model: string;
  jobs: number;
  completed: number;
  failed: number;
  credits_charged: number;
  usage: Record<string, number>;
  estimated_provider_usd: number | null;
}

export interface UsageReport {
  period_days: number;
  rows: UsageRow[];
  note: string;
}

export interface AuditEvent {
  id: string;
  actor_user_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  ip_address: string | null;
  details: Record<string, unknown> | null;
  created_at: string | null;
}

// ---- Billing (prices are integer minor units; see lib/money.ts) ----------------------

export interface MoneyValue {
  amount_minor: number;
  currency: string;
  formatted: string;
}

/** A USD price plus its KES reference amount, both calculated by the server. */
export interface PriceWithReference extends MoneyValue {
  reference: MoneyValue & { rate: string; label: string };
}

export type BillingUnavailableReason =
  | "free_plan" | "credits_not_configured" | "paystack_plan_not_configured";

export interface BillingPlan {
  code: string;
  name: string;
  summary: string;
  interval: "month";
  price: PriceWithReference;
  monthly_credits: number | null;
  purchasable: boolean;
  unavailable_reason: BillingUnavailableReason | null;
}

export interface CreditPackage {
  code: string;
  name: string;
  price: PriceWithReference;
  credits: number | null;
  purchasable: boolean;
  unavailable_reason: BillingUnavailableReason | null;
}

export interface CurrencyInfo {
  display_currency: string;
  reference_currency: string;
  usd_to_kes_reference_rate: string;
  reference_note: string;
}

export interface CheckoutStatus {
  enabled: boolean;
  reason: "payments_not_configured" | "usd_checkout_not_enabled" | null;
  message: string | null;
  mode?: "test" | "live" | "unknown" | null;
}

export interface BillingCatalog {
  currency: CurrencyInfo;
  plans: BillingPlan[];
  credit_packages: CreditPackage[];
  checkout: CheckoutStatus;
}

export type PaymentStatus = "pending" | "succeeded" | "failed" | "mismatch";
export type PaymentKind = "credit_package" | "subscription" | "subscription_renewal";

export interface Payment {
  id: string;
  reference: string;
  kind: PaymentKind;
  item_code: string;
  item_name: string;
  status: PaymentStatus;
  price: MoneyValue & { reference?: MoneyValue & { rate: string; label: string } };
  amount_paid: MoneyValue | null;
  credits: number;
  credits_granted: boolean;
  channel: string | null;
  failure_reason: string | null;
  created_at: string;
  paid_at: string | null;
}

export interface AdminPayment extends Payment {
  user_id: string;
  provider_transaction_id: string | null;
}

export type SubscriptionStatus = "active" | "non_renewing" | "past_due" | "cancelled";

export interface SubscriptionInfo {
  plan_code: string;
  status: SubscriptionStatus;
  current_period_end: string | null;
  linked_to_paystack: boolean;
}

export interface BillingOverview {
  subscription: SubscriptionInfo | null;
  plan: BillingPlan | null;
  credits: CreditAccount;
  checkout: CheckoutStatus;
  currency: CurrencyInfo;
  recent_payments: Payment[];
}

// ---- Admin pricing ------------------------------------------------------------------

export interface ReferenceJob {
  name: string;
  usage: Record<string, number>;
  credits: number | null;
  provider_usd: number | null;
}

export interface AdminGenerationPrice {
  provider: string;
  provider_label: string;
  configured: boolean;
  credential_env: string;
  model: string;
  label: string;
  kind: GenerationKind;
  usage_metrics: string[];
  source: "admin" | "file" | "override" | null;
  enabled: boolean;
  price: {
    credits_per_1000: Record<string, number>;
    minimum_credits: number;
    provider_usd_per_1000: Record<string, number> | null;
    provider_price_source: string | null;
  } | null;
  reference_jobs: ReferenceJob[];
}

export interface AdminSaleItem {
  item_type: "plan" | "credit_package";
  code: string;
  name: string;
  price: MoneyValue;
  credits: number | null;
  usd_per_credit: number | null;
  net_revenue_usd: number;
  max_provider_cost_usd: number | null;
  gross_margin_percent: number | null;
  paystack_plan_code?: string | null;
  monthly_credit_limit?: number | null;
}

export interface AdminPricing {
  generation: AdminGenerationPrice[];
  plans: AdminSaleItem[];
  credit_packages: AdminSaleItem[];
  assumptions: { payment_fee_percent: string; worst_case_provider_usd_per_credit: number | null; explanation: string };
}

export interface GenerationPriceInput {
  credits_per_1000: Record<string, number>;
  minimum_credits: number;
  provider_usd_per_1000: Record<string, number> | null;
  provider_price_source: string | null;
  enabled: boolean;
}
