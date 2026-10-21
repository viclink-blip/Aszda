"use client";

import Link from "next/link";
import { LoadingRows } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import type { GenerationKind } from "@/lib/types";
import { JobItem } from "./job-item";

/** The last few jobs of one kind. Change `refreshKey` to reload. */
export function RecentJobs({ kind, refreshKey, excludeId }: { kind: GenerationKind; refreshKey: number; excludeId?: string }) {
  const { data, loading, reload } = useApi(() => api.generation.list({ kind, limit: 5 }), [kind, refreshKey]);
  const jobs = (data?.items ?? []).filter((j) => j.id !== excludeId);

  return (
    <section aria-labelledby={`recent-${kind}`} className="mt-8">
      <div className="mb-3 flex items-center justify-between">
        <h2 id={`recent-${kind}`} className="text-sm font-semibold text-fg">Recent in this studio</h2>
        <Link href={`/app/generations?kind=${kind}`} className="text-sm text-muted hover:text-fg">See all</Link>
      </div>
      {loading && !data ? (
        <LoadingRows rows={2} />
      ) : jobs.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line-strong px-4 py-6 text-center text-sm text-muted">
          Your generations from this studio will appear here.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {jobs.map((job) => <JobItem key={job.id} job={job} onRetried={() => void reload()} />)}
        </ul>
      )}
    </section>
  );
}
