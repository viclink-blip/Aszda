/** Small formatting helpers and human-readable labels for API values. */

import type { CreditTxType, GenerationKind, JobStatus, ProjectStatus, UnavailableReason } from "./types";

export function formatDate(iso: string | null | undefined, withTime = false): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, withTime
    ? { dateStyle: "medium", timeStyle: "short" }
    : { dateStyle: "medium" });
}

/** "3 minutes ago", "yesterday", ... falls back to a date after a week. */
export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const seconds = Math.round((then - Date.now()) / 1000);
  const abs = Math.abs(seconds);
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (abs < 60) return rtf.format(seconds, "second");
  if (abs < 3600) return rtf.format(Math.round(seconds / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(seconds / 3600), "hour");
  if (abs < 7 * 86400) return rtf.format(Math.round(seconds / 86400), "day");
  return formatDate(iso);
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat().format(value);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: "Draft",
  in_progress: "In progress",
  completed: "Completed",
  archived: "Archived",
};

export const JOB_STATUS_LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  validating: "Validating",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export const KIND_LABELS: Record<GenerationKind, string> = {
  text: "Writing",
  image: "Image",
  video: "Video",
  animation: "Animation",
  speech: "Voice",
};

export const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic Claude",
  openai: "OpenAI",
  runway: "Runway",
  google: "Google Veo",
};

export function providerLabel(name: string): string {
  return PROVIDER_LABELS[name] ?? name;
}

/** Plain-language explanation of each credit ledger entry type. */
export const CREDIT_TX_INFO: Record<CreditTxType, { label: string; explanation: string }> = {
  grant: { label: "Grant", explanation: "Credits added by ASZDA (for example the free sign-up credits). They never expire." },
  purchase: { label: "Purchase", explanation: "Credits from a credit package you bought. They never expire." },
  plan_allowance: { label: "Plan credits", explanation: "Your plan's monthly credits. They expire at the end of the billing period." },
  expire: { label: "Expired", explanation: "Unused plan credits removed at the end of their billing period (they do not roll over)." },
  reserve: { label: "Reserved", explanation: "Credits held when a generation starts, based on its maximum estimated cost." },
  release: { label: "Released", explanation: "The unused part of a reservation, returned after a generation finished." },
  refund: { label: "Refund", explanation: "A reservation returned in full because a generation failed or was cancelled." },
  adjustment: { label: "Adjustment", explanation: "A manual correction made by an ASZDA administrator." },
};

export const UNAVAILABLE_REASONS: Record<UnavailableReason, string> = {
  provider_not_configured:
    "This provider is not connected yet. An administrator needs to add its API key before it can be used.",
  pricing_not_configured:
    "Credit pricing for this model has not been set yet, so it cannot be used until an administrator configures it.",
  provider_disabled: "An administrator has switched this provider off.",
  model_retired: "The provider has retired this model.",
  unsupported_model: "This model is not offered for this kind of generation.",
};

export function unavailableText(reason: UnavailableReason | null): string {
  return reason ? UNAVAILABLE_REASONS[reason] : "This model is not available right now.";
}
