"use client";

import { Coins } from "lucide-react";
import { useState } from "react";
import { Badge, type Tone } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { LoadingRows, Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { CREDIT_TX_INFO, formatDate, formatNumber } from "@/lib/format";
import type { CreditTransaction, CreditTxType } from "@/lib/types";

const PAGE_SIZE = 25;

const TX_TONES: Record<CreditTxType, Tone> = {
  grant: "success", purchase: "success", reserve: "info", release: "neutral", refund: "neutral", adjustment: "warning",
};

/** The ledger as a table (desktop) or a list (mobile). */
export function LedgerTable({ items }: { items: CreditTransaction[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-subtle uppercase">
            <th scope="col" className="px-5 py-2.5 font-medium">Date</th>
            <th scope="col" className="px-3 py-2.5 font-medium">Type</th>
            <th scope="col" className="px-3 py-2.5 font-medium">Details</th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">Change</th>
            <th scope="col" className="px-5 py-2.5 text-right font-medium">Balance</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {items.map((tx) => (
            <tr key={tx.id}>
              <td className="px-5 py-3 whitespace-nowrap text-muted">{formatDate(tx.created_at, true)}</td>
              <td className="px-3 py-3"><Badge tone={TX_TONES[tx.type]}>{CREDIT_TX_INFO[tx.type].label}</Badge></td>
              <td className="max-w-xs px-3 py-3 text-muted">
                {tx.reason || (tx.generation_job_id ? "Generation" : "—")}
              </td>
              <td className={`px-3 py-3 text-right font-mono tabular-nums ${tx.amount > 0 ? "text-success" : tx.amount < 0 ? "text-fg" : "text-muted"}`}>
                {tx.amount > 0 ? "+" : ""}{formatNumber(tx.amount)}
              </td>
              <td className="px-5 py-3 text-right font-mono text-muted tabular-nums">{formatNumber(tx.balance_after)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CreditsView() {
  const [offset, setOffset] = useState(0);
  const { data, error, reload } = useApi(() => api.me.credits({ limit: PAGE_SIZE, offset }), [offset]);

  return (
    <>
      <PageHeader title="Credits" description="Credits pay for generations. Here is your balance and every change to it." />
      <Notice tone="info" title="Payments are not active yet" className="mb-6">
        You cannot buy credits yet — the credits-based pricing is still being designed. During this early period,
        credits are granted by ASZDA.
      </Notice>

      {error && !data ? (
        <ErrorState error={error} onRetry={reload} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
          <Card className="order-2 lg:order-1">
            <CardHeader title="Ledger" description="Newest first." />
            {!data ? (
              <div className="p-5"><LoadingRows rows={4} /></div>
            ) : data.transactions.items.length === 0 ? (
              <EmptyState className="m-5" icon={Coins} title="No credit activity yet" description="Grants, reservations, charges and refunds will be listed here." />
            ) : (
              <>
                <LedgerTable items={data.transactions.items} />
                <div className="px-5 pb-4">
                  <Pagination offset={offset} limit={PAGE_SIZE} total={data.transactions.total} onChange={setOffset} />
                </div>
              </>
            )}
          </Card>
          <div className="order-1 flex flex-col gap-6 lg:order-2">
            <Card>
              <CardBody>
                <p className="text-xs font-medium tracking-wide text-subtle uppercase">Current balance</p>
                {data ? (
                  <p className="mt-2 font-display text-4xl font-semibold text-fg tabular-nums">{formatNumber(data.account.balance)}</p>
                ) : (
                  <Skeleton className="mt-2 h-10 w-24" />
                )}
                <p className="mt-1 text-sm text-muted">credits</p>
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="What the entries mean" />
              <CardBody>
                <dl className="flex flex-col gap-3 text-sm">
                  {(Object.keys(CREDIT_TX_INFO) as CreditTxType[]).map((type) => (
                    <div key={type}>
                      <dt><Badge tone={TX_TONES[type]}>{CREDIT_TX_INFO[type].label}</Badge></dt>
                      <dd className="mt-1 text-muted">{CREDIT_TX_INFO[type].explanation}</dd>
                    </div>
                  ))}
                </dl>
              </CardBody>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
