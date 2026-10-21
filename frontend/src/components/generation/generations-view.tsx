"use client";

import { History } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { ButtonLink } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { LoadingRows } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { JOB_STATUS_LABELS, KIND_LABELS } from "@/lib/format";
import type { GenerationKind, JobStatus } from "@/lib/types";
import { JobItem } from "./job-item";

const PAGE_SIZE = 20;

export function GenerationsView() {
  const initialKind = useSearchParams().get("kind") as GenerationKind | null;
  const [kind, setKind] = useState<GenerationKind | "">(initialKind && initialKind in KIND_LABELS ? initialKind : "");
  const [status, setStatus] = useState<JobStatus | "">("");
  const [offset, setOffset] = useState(0);
  const { data, error, reload } = useApi(
    () => api.generation.list({ kind, status, limit: PAGE_SIZE, offset }),
    [kind, status, offset],
  );

  return (
    <>
      <PageHeader title="Generations" description="Every generation you have started, with live status, results, cancel and retry." />
      <div className="mb-6 flex flex-col gap-3 sm:flex-row">
        <div className="sm:w-48">
          <Select aria-label="Filter by type" value={kind} onChange={(e) => { setKind(e.target.value as GenerationKind | ""); setOffset(0); }}>
            <option value="">All types</option>
            {(["text", "video", "speech"] as GenerationKind[]).map((k) => <option key={k} value={k}>{KIND_LABELS[k]}</option>)}
          </Select>
        </div>
        <div className="sm:w-48">
          <Select aria-label="Filter by status" value={status} onChange={(e) => { setStatus(e.target.value as JobStatus | ""); setOffset(0); }}>
            <option value="">All statuses</option>
            {Object.entries(JOB_STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>
        </div>
      </div>
      {error && !data ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !data ? (
        <LoadingRows rows={4} label="Loading generations" />
      ) : data.items.length === 0 ? (
        kind || status ? (
          <EmptyState icon={History} title="No generations match these filters" />
        ) : (
          <EmptyState
            icon={History}
            title="No generations yet"
            description="Start in a studio — scripts, video clips, animations and voice-overs all appear here."
            action={<ButtonLink href="/app/studio/script">Open Script Studio</ButtonLink>}
          />
        )
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {data.items.map((job) => <JobItem key={job.id} job={job} onRetried={() => void reload()} />)}
          </ul>
          <Pagination offset={offset} limit={PAGE_SIZE} total={data.total} onChange={setOffset} />
        </>
      )}
    </>
  );
}
