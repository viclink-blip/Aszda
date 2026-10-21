"use client";

import { useState } from "react";
import { StatusBadge } from "@/components/ui/badge";
import { ErrorState } from "@/components/ui/error-state";
import { Select } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { LoadingRows } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatDate, formatNumber, JOB_STATUS_LABELS, KIND_LABELS, providerLabel } from "@/lib/format";
import type { JobStatus } from "@/lib/types";

const PAGE_SIZE = 25;

export function AdminJobs() {
  const [status, setStatus] = useState<JobStatus | "">("");
  const [offset, setOffset] = useState(0);
  const { data, error, reload } = useApi(() => api.admin.jobs({ status, limit: PAGE_SIZE, offset }), [status, offset]);

  return (
    <>
      <div className="mb-4 w-52">
        <Select aria-label="Filter by status" value={status} onChange={(e) => { setStatus(e.target.value as JobStatus | ""); setOffset(0); }}>
          <option value="">All statuses</option>
          {Object.entries(JOB_STATUS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </Select>
      </div>
      {error && !data ? <ErrorState error={error} onRetry={reload} /> : !data ? <LoadingRows rows={5} /> : (
        <>
          <div className="overflow-x-auto rounded-xl border border-line bg-surface">
            <table className="w-full min-w-[52rem] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-subtle uppercase">
                  <th scope="col" className="px-4 py-2.5 font-medium">Created</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Type / model</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Status</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Reserved</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Charged</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">User / error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.items.map((j) => (
                  <tr key={j.id}>
                    <td className="px-4 py-3 whitespace-nowrap text-muted">{formatDate(j.created_at, true)}</td>
                    <td className="px-3 py-3"><p className="text-fg">{KIND_LABELS[j.kind]}</p><p className="text-xs text-subtle">{providerLabel(j.provider)} · {j.model}</p></td>
                    <td className="px-3 py-3"><StatusBadge status={j.status} /></td>
                    <td className="px-3 py-3 text-right font-mono tabular-nums">{formatNumber(j.credits_reserved)}</td>
                    <td className="px-3 py-3 text-right font-mono tabular-nums">{formatNumber(j.credits_charged)}</td>
                    <td className="max-w-xs px-4 py-3">
                      <p className="truncate font-mono text-xs text-subtle">{j.user_id}</p>
                      {j.error && <p className="text-xs text-danger">{j.error.code}: {j.error.message}</p>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.items.length === 0 && <p className="p-6 text-center text-sm text-muted">No jobs.</p>}
          </div>
          <Pagination offset={offset} limit={PAGE_SIZE} total={data.total} onChange={setOffset} />
        </>
      )}
    </>
  );
}
