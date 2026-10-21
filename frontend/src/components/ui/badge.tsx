import { cn } from "@/lib/cn";
import { JOB_STATUS_LABELS, PROJECT_STATUS_LABELS } from "@/lib/format";
import type { JobStatus, ProjectStatus } from "@/lib/types";

export type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "info";

const TONES: Record<Tone, string> = {
  neutral: "bg-surface-2 text-muted border-line",
  accent: "bg-accent-soft text-accent border-accent/20",
  success: "bg-success-soft text-success border-success/20",
  warning: "bg-warning-soft text-warning border-warning/20",
  danger: "bg-danger-soft text-danger border-danger/20",
  info: "bg-info-soft text-info border-info/20",
};

export function Badge({ tone = "neutral", className, children, dot }: {
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
  /** Show a small dot (pulsing when "live"). */
  dot?: boolean | "live";
}) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
      TONES[tone], className,
    )}>
      {dot && (
        <span className={cn("h-1.5 w-1.5 rounded-full bg-current", dot === "live" && "animate-pulse")} aria-hidden />
      )}
      {children}
    </span>
  );
}

const JOB_TONES: Record<JobStatus, Tone> = {
  queued: "neutral",
  validating: "info",
  processing: "info",
  completed: "success",
  failed: "danger",
  cancelled: "warning",
};

const PROJECT_TONES: Record<ProjectStatus, Tone> = {
  draft: "neutral",
  in_progress: "info",
  completed: "success",
  archived: "warning",
};

/** Colour-coded status for jobs and projects (text label, never colour alone). */
export function StatusBadge({ status }: { status: JobStatus | ProjectStatus }) {
  if (status in JOB_TONES) {
    const s = status as JobStatus;
    const live = s === "queued" || s === "validating" || s === "processing";
    return <Badge tone={JOB_TONES[s]} dot={live ? "live" : true}>{JOB_STATUS_LABELS[s]}</Badge>;
  }
  const p = status as ProjectStatus;
  return <Badge tone={PROJECT_TONES[p]} dot>{PROJECT_STATUS_LABELS[p]}</Badge>;
}

/** "Planned" label for features that do not exist yet. */
export function PlannedBadge({ children = "Planned" }: { children?: React.ReactNode }) {
  return <Badge tone="warning">{children}</Badge>;
}
