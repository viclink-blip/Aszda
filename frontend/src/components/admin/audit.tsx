"use client";

import { useState } from "react";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { LoadingRows } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useDebounced } from "@/hooks/use-debounced";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";

const PAGE_SIZE = 50;

export function AdminAudit() {
  const [action, setAction] = useState("");
  const [offset, setOffset] = useState(0);
  const a = useDebounced(action.trim());
  const { data, error, reload } = useApi(() => api.admin.auditEvents({ action: a, limit: PAGE_SIZE, offset }), [a, offset]);

  return (
    <>
      <div className="mb-4 max-w-sm">
        <Input aria-label="Filter by exact action" placeholder="Exact action, e.g. admin.user_updated" value={action}
          onChange={(e) => { setAction(e.target.value); setOffset(0); }} />
      </div>
      {error && !data ? <ErrorState error={error} onRetry={reload} /> : !data ? <LoadingRows rows={5} /> : (
        <>
          <div className="overflow-x-auto rounded-xl border border-line bg-surface">
            <table className="w-full min-w-[48rem] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-subtle uppercase">
                  <th scope="col" className="px-4 py-2.5 font-medium">When</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Action</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Target</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">IP</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.items.map((e) => (
                  <tr key={e.id} className="align-top">
                    <td className="px-4 py-3 whitespace-nowrap text-muted">{formatDate(e.created_at, true)}</td>
                    <td className="px-3 py-3 font-mono text-xs text-fg">{e.action}</td>
                    <td className="px-3 py-3 text-xs text-muted">{e.target_type ? `${e.target_type} ${e.target_id ?? ""}` : "—"}</td>
                    <td className="px-3 py-3 font-mono text-xs text-muted">{e.ip_address ?? "—"}</td>
                    <td className="max-w-sm px-4 py-3">
                      {/* Shown as plain text, never as HTML. */}
                      <pre className="font-mono text-xs break-all whitespace-pre-wrap text-muted">{e.details && Object.keys(e.details).length ? JSON.stringify(e.details, null, 1) : "—"}</pre>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.items.length === 0 && <p className="p-6 text-center text-sm text-muted">No events.</p>}
          </div>
          <Pagination offset={offset} limit={PAGE_SIZE} total={data.total} onChange={setOffset} />
        </>
      )}
    </>
  );
}
