"use client";

import { useState } from "react";
import { ErrorState } from "@/components/ui/error-state";
import { Select } from "@/components/ui/input";
import { Notice } from "@/components/ui/notice";
import { LoadingRows } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatNumber, providerLabel } from "@/lib/format";

export function AdminUsage() {
  const [days, setDays] = useState(30);
  const { data, error, reload } = useApi(() => api.admin.usage(days), [days]);

  return (
    <>
      <div className="mb-4 w-44">
        <Select aria-label="Period" value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {[7, 30, 90, 365].map((d) => <option key={d} value={d}>Last {d} days</option>)}
        </Select>
      </div>
      <Notice tone="warning" title="Estimated provider cost is an estimate" className="mb-4">
        {data?.note ?? "Estimated provider USD comes from configured provider prices; it is not an invoice."}
      </Notice>
      {error && !data ? <ErrorState error={error} onRetry={reload} /> : !data ? <LoadingRows rows={3} /> : (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full min-w-[48rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-subtle uppercase">
                <th scope="col" className="px-4 py-2.5 font-medium">Provider / model</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Jobs</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Completed</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Failed</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Credits</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Usage</th>
                <th scope="col" className="px-4 py-2.5 text-right font-medium">Est. provider USD</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.rows.map((r) => (
                <tr key={`${r.provider}/${r.model}`}>
                  <td className="px-4 py-3"><p className="text-fg">{providerLabel(r.provider)}</p><p className="text-xs text-subtle">{r.model}</p></td>
                  <td className="px-3 py-3 text-right tabular-nums">{r.jobs}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{r.completed}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{r.failed}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{formatNumber(r.credits_charged)}</td>
                  <td className="px-3 py-3 text-xs text-muted">
                    {Object.entries(r.usage).map(([k, v]) => <span key={k} className="block">{k}: {formatNumber(v)}</span>)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {r.estimated_provider_usd === null ? <span className="text-subtle">not priced</span> : <>≈ ${r.estimated_provider_usd.toFixed(2)} <span className="text-xs text-subtle">(estimate)</span></>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.rows.length === 0 && <p className="p-6 text-center text-sm text-muted">No settled jobs in this period.</p>}
        </div>
      )}
    </>
  );
}
