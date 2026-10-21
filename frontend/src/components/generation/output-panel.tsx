"use client";

import { ArrowRight, Clapperboard } from "lucide-react";
import Link from "next/link";
import type { Job } from "@/lib/types";
import { JobItem } from "./job-item";

/** Right-hand panel of a studio: the job just started, followed live. */
export function OutputPanel({ job, onRetried, emptyText }: { job: Job | null; onRetried: (job: Job) => void; emptyText: string }) {
  return (
    <section aria-labelledby="output-heading" className="flex flex-col gap-3">
      <h2 id="output-heading" className="text-sm font-semibold text-fg">Output</h2>
      {job ? (
        <>
          <ul aria-live="polite">
            <JobItem key={job.id} job={job} defaultOpen onRetried={onRetried} />
          </ul>
          {job.project_id && (
            <Link href={`/app/projects/${job.project_id}?tab=generations`} className="inline-flex items-center gap-1.5 self-start text-sm font-medium text-accent hover:underline">
              View in project <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
          )}
        </>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line-strong px-6 py-14 text-center">
          <Clapperboard className="h-6 w-6 text-subtle" aria-hidden />
          <p className="mt-3 max-w-xs text-sm text-muted">{emptyText}</p>
        </div>
      )}
    </section>
  );
}
