"use client";

import { AudioLines, ChevronDown, ExternalLink, Film, PenLine, RotateCcw, Square, Wand2 } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/components/ui/toast";
import { useJobPolling } from "@/hooks/use-job-polling";
import { api, ApiError, errorMessage, newIdempotencyKey } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatNumber, formatRelative, KIND_LABELS, providerLabel } from "@/lib/format";
import { isJobActive, type GenerationKind, type Job } from "@/lib/types";
import { ContinueConversation } from "./continue-conversation";
import { JobResult } from "./job-result";

const KIND_ICONS: Record<GenerationKind, typeof Film> = {
  text: PenLine, image: Film, video: Film, animation: Wand2, speech: AudioLines,
};

/** A short, readable summary of what was asked for. */
function jobSummary(job: Job): string {
  const p = job.params;
  const text = (p.prompt ?? p.prompt_text ?? p.text) as string | undefined;
  return text ? text.slice(0, 140) : "";
}

function creditsText(job: Job): string {
  if (job.credits_charged !== null && job.credits_charged !== undefined) return `${formatNumber(job.credits_charged)} credits charged`;
  if (isJobActive(job.status)) return `${formatNumber(job.credits_reserved)} credits reserved`;
  return "No credits charged";
}

/**
 * One generation job with live status. Active jobs refresh themselves every few
 * seconds. Offers cancel (while running), retry (after failure) and the result.
 */
export function JobItem({ job: initial, onRetried, onContinued, showProject = true, defaultOpen = false }: {
  job: Job;
  /** Called with the new job created by "Retry". */
  onRetried?: (job: Job) => void;
  /** When set, a finished text answer can be replied to; called with the new job. */
  onContinued?: (job: Job) => void;
  showProject?: boolean;
  defaultOpen?: boolean;
}) {
  const { job, setJob, pollError } = useJobPolling(initial);
  const toast = useToast();
  const [open, setOpen] = useState(defaultOpen);
  const [busy, setBusy] = useState<"cancel" | "retry" | null>(null);
  // Reused if a retry fails because of the network, so the server can de-duplicate it.
  const retryKey = useRef<string | null>(null);
  if (!job) return null;

  const Icon = KIND_ICONS[job.kind];
  const active = isJobActive(job.status);
  const canRetry = job.status === "failed" || job.status === "cancelled";

  const cancel = async () => {
    setBusy("cancel");
    try {
      const { job: updated } = await api.generation.cancel(job.id);
      setJob(updated);
      toast.success("Generation cancelled", "Any reserved credits were returned.");
    } catch (error) {
      toast.error("Could not cancel", errorMessage(error));
    } finally {
      setBusy(null);
    }
  };

  const retry = async () => {
    setBusy("retry");
    retryKey.current ??= newIdempotencyKey();
    try {
      const { job: created } = await api.generation.retry(job.id, retryKey.current);
      retryKey.current = null;
      toast.success("Retry started");
      onRetried?.(created);
    } catch (error) {
      if (!(error instanceof ApiError && error.isNetworkError)) retryKey.current = null;
      toast.error("Could not retry", errorMessage(error));
    } finally {
      setBusy(null);
    }
  };

  const summary = jobSummary(job);

  return (
    <li className="rounded-xl border border-line bg-surface">
      <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-muted">
          <Icon className="h-4 w-4" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-sm font-medium text-fg">{KIND_LABELS[job.kind]}</span>
            <span className="text-xs text-subtle">{providerLabel(job.provider)} · {job.model}</span>
            <StatusBadge status={job.status} />
          </div>
          {summary && <p className="mt-1 line-clamp-2 text-sm text-muted">{summary}</p>}
          <p className="mt-1 text-xs text-subtle">
            Started {formatRelative(job.created_at)} · {creditsText(job)}
            {job.retry_of_id && " · retry"}
          </p>
          {active && (
            <div className="mt-3 max-w-md">
              <Progress value={job.progress} label={`Progress of ${KIND_LABELS[job.kind].toLowerCase()} generation`} />
              <p className="mt-1 text-xs text-subtle">
                {job.progress !== null ? `${job.progress}%` : "Working…"} {pollError && <span className="text-warning">· {pollError}</span>}
              </p>
            </div>
          )}
          {job.error && (
            <p className="mt-2 text-sm text-danger">{job.error.message}</p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
          {showProject && job.project_id && (
            <Link href={`/app/projects/${job.project_id}?tab=generations`} className="inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
              Project <ExternalLink className="h-3 w-3" aria-hidden />
            </Link>
          )}
          {active && (
            <Button size="sm" variant="outline" onClick={cancel} loading={busy === "cancel"}>
              <Square className="h-3.5 w-3.5" aria-hidden /> Cancel
            </Button>
          )}
          {canRetry && (
            <Button size="sm" variant="outline" onClick={retry} loading={busy === "retry"}>
              <RotateCcw className="h-3.5 w-3.5" aria-hidden /> Retry
            </Button>
          )}
          {job.status === "completed" && (
            <Button size="sm" variant="ghost" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
              {open ? "Hide result" : "View result"}
              <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} aria-hidden />
            </Button>
          )}
        </div>
      </div>
      {open && job.status === "completed" && (
        <div className="border-t border-line p-4">
          <JobResult job={job} />
          {onContinued && job.kind === "text" && job.params.task !== "director_plan" && (
            <ContinueConversation job={job} onStarted={onContinued} />
          )}
        </div>
      )}
    </li>
  );
}
