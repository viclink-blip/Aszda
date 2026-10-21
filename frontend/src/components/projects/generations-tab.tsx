"use client";

import { History, RefreshCw } from "lucide-react";
import { useState } from "react";
import { JobItem } from "@/components/generation/job-item";
import { Button, ButtonLink } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingRows } from "@/components/ui/skeleton";
import { Pagination } from "@/components/ui/pagination";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import type { ProjectTabProps } from "./project-workspace";

const PAGE_SIZE = 20;

export function GenerationsTab({ detail }: ProjectTabProps) {
  const projectId = detail.project.id;
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useApi(
    () => api.projects.jobs(projectId, { limit: PAGE_SIZE, offset }),
    [projectId, offset],
  );

  return (
    <section aria-labelledby="generations-heading">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="generations-heading" className="font-display text-lg font-semibold text-fg">Generations</h2>
          <p className="text-sm text-muted">Everything generated for this project, with live status.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void reload()} loading={loading && Boolean(data)}>
          <RefreshCw className="h-4 w-4" aria-hidden /> Refresh
        </Button>
      </div>
      {error && !data ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !data ? (
        <LoadingRows rows={3} label="Loading generations" />
      ) : data.items.length === 0 ? (
        <EmptyState
          icon={History}
          title="No generations yet"
          description="Open a studio from this project to write, generate video, animate a character or record a voice."
          action={<ButtonLink href={`/app/studio/script?project=${projectId}`} variant="outline" size="sm">Open Script Studio</ButtonLink>}
        />
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {data.items.map((job) => <JobItem key={job.id} job={job} showProject={false} onRetried={() => void reload()} />)}
          </ul>
          <Pagination offset={offset} limit={PAGE_SIZE} total={data.total} onChange={setOffset} />
        </>
      )}
    </section>
  );
}
