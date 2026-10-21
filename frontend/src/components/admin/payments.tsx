"use client";

import { Receipt } from "lucide-react";
import { useState } from "react";
import { PAYMENT_KIND, PAYMENT_STATUS, chargedAmount } from "@/components/billing/payment-history";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Notice } from "@/components/ui/notice";
import { Pagination } from "@/components/ui/pagination";
import { LoadingRows } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import { formatMoney } from "@/lib/money";
import type { PaymentStatus } from "@/lib/types";

const PAGE_SIZE = 25;

export function AdminPayments() {
  const [status, setStatus] = useState<PaymentStatus | "">("");
  const [offset, setOffset] = useState(0);
  const { data, error, reload } = useApi(() => api.admin.payments({ status, limit: PAGE_SIZE, offset }), [status, offset]);

  return (
    <>
      {data && (
        <Notice tone={data.checkout.enabled ? "success" : "info"} className="mb-6"
          title={data.checkout.enabled ? `Checkout is open (${data.checkout.mode ?? "?"} mode, USD)` : "Checkout is closed"}>
          {data.checkout.enabled ? "Payments are verified with Paystack for the exact USD amount before credits are added."
            : data.checkout.message}
        </Notice>
      )}
      <Card>
        <CardHeader title="Payments" description="'Under review' means money arrived but did not match the expected amount, currency or plan — nothing was granted. Check it in the Paystack dashboard."
          action={
            <select aria-label="Filter by status" value={status}
              onChange={(e) => { setStatus(e.target.value as PaymentStatus | ""); setOffset(0); }}
              className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm">
              <option value="">All</option>
              {(Object.keys(PAYMENT_STATUS) as PaymentStatus[]).map((s) => <option key={s} value={s}>{PAYMENT_STATUS[s].label}</option>)}
            </select>
          } />
        {error && !data ? <div className="m-5"><ErrorState error={error} onRetry={reload} /></div> : !data ? (
          <div className="p-5"><LoadingRows rows={5} /></div>
        ) : data.items.length === 0 ? (
          <EmptyState className="m-5" icon={Receipt} title="No payments" description="Payments appear here once customers check out." />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[56rem] text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-subtle uppercase">
                    <th scope="col" className="px-5 py-2.5 font-medium">Date</th>
                    <th scope="col" className="px-3 py-2.5 font-medium">User</th>
                    <th scope="col" className="px-3 py-2.5 font-medium">Item</th>
                    <th scope="col" className="px-3 py-2.5 font-medium">Status</th>
                    <th scope="col" className="px-3 py-2.5 text-right font-medium">Expected</th>
                    <th scope="col" className="px-3 py-2.5 text-right font-medium">Paid</th>
                    <th scope="col" className="px-3 py-2.5 text-right font-medium">Credits</th>
                    <th scope="col" className="px-5 py-2.5 font-medium">Reference</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data.items.map((p) => (
                    <tr key={p.id}>
                      <td className="px-5 py-3 whitespace-nowrap text-muted">{formatDate(p.paid_at ?? p.created_at, true)}</td>
                      <td className="px-3 py-3 font-mono text-xs text-muted">{p.user_id.slice(0, 8)}</td>
                      <td className="px-3 py-3">{p.item_name} <span className="text-muted">· {PAYMENT_KIND[p.kind]}</span></td>
                      <td className="px-3 py-3"><Badge tone={PAYMENT_STATUS[p.status].tone}>{PAYMENT_STATUS[p.status].label}</Badge></td>
                      <td className="px-3 py-3 text-right font-mono tabular-nums">{formatMoney(p.price)} {p.price.currency}</td>
                      <td className="px-3 py-3 text-right font-mono tabular-nums">
                        {p.amount_paid ? `${chargedAmount(p)} ${p.amount_paid.currency}` : "—"}
                      </td>
                      <td className="px-3 py-3 text-right font-mono tabular-nums">
                        {p.credits ? `${formatNumber(p.credits)}${p.credits_granted ? " ✓" : ""}` : "—"}
                      </td>
                      <td className="px-5 py-3 font-mono text-xs break-all text-muted">{p.reference}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="px-5 pb-4"><Pagination offset={offset} limit={PAGE_SIZE} total={data.total} onChange={setOffset} /></div>
          </>
        )}
      </Card>
    </>
  );
}
