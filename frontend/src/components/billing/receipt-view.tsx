"use client";

import { useParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingRows } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import { formatMoney } from "@/lib/money";
import { PAYMENT_KIND, PAYMENT_STATUS } from "./payment-history";

/** A printable receipt. It states the amount and currency Paystack actually confirmed. */
export function ReceiptView() {
  const { id } = useParams<{ id: string }>();
  const { data, error, reload } = useApi(() => api.billing.payment(id), [id]);

  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return <LoadingRows rows={6} />;
  const p = data.payment;
  const rows: [string, React.ReactNode][] = [
    ["Seller", `${data.seller.name} — ${data.seller.product}`],
    ["Item", `${p.item_name} (${PAYMENT_KIND[p.kind]})`],
    ["Price", `${formatMoney(p.price)} USD${p.kind !== "credit_package" ? " per month" : ""}`],
    ["Amount charged", p.amount_paid ? `${formatMoney(p.amount_paid)} ${p.amount_paid.currency}` : "Not charged"],
    ["Credits", p.credits ? `${formatNumber(p.credits)}${p.credits_granted ? " (added)" : ""}` : "—"],
    ["Status", <Badge key="s" tone={PAYMENT_STATUS[p.status].tone}>{PAYMENT_STATUS[p.status].label}</Badge>],
    ["Paid on", p.paid_at ? formatDate(p.paid_at, true) : "—"],
    ["Payment method", p.channel ? `Paystack (${p.channel})` : "Paystack"],
    ["Reference", <span key="r" className="font-mono text-xs break-all">{p.reference}</span>],
  ];

  return (
    <div className="mx-auto max-w-xl">
      <Card>
        <CardBody>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-medium tracking-wide text-subtle uppercase">
                {p.status === "succeeded" ? "Receipt" : "Payment details"}
              </p>
              <p className="mt-1 font-display text-3xl font-semibold text-fg tabular-nums">
                {formatMoney(p.amount_paid ?? p.price)} <span className="text-base text-muted">USD</span>
              </p>
              {p.price.reference && (
                <p className="mt-1 text-xs text-subtle">≈ {formatMoney(p.price.reference)} · {p.price.reference.label}</p>
              )}
            </div>
            <span className="font-display text-lg font-semibold text-fg">ASZDA</span>
          </div>
          <dl className="mt-6 divide-y divide-line text-sm">
            {rows.map(([label, value]) => (
              <div key={label} className="flex justify-between gap-4 py-2.5">
                <dt className="text-muted">{label}</dt>
                <dd className="text-right text-fg">{value}</dd>
              </div>
            ))}
          </dl>
          {p.failure_reason && <p className="mt-4 text-sm text-warning">{p.failure_reason}</p>}
        </CardBody>
      </Card>
      <div className="mt-4 flex gap-2 print:hidden">
        <ButtonLink href="/app/billing" variant="secondary">Back to billing</ButtonLink>
        <Button variant="ghost" onClick={() => window.print()}>Print</Button>
      </div>
    </div>
  );
}
