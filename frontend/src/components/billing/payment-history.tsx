import Link from "next/link";
import { Badge, type Tone } from "@/components/ui/badge";
import { formatDate, formatNumber } from "@/lib/format";
import { formatMoney } from "@/lib/money";
import type { Payment, PaymentKind, PaymentStatus } from "@/lib/types";

export const PAYMENT_STATUS: Record<PaymentStatus, { label: string; tone: Tone }> = {
  pending: { label: "Pending", tone: "info" },
  succeeded: { label: "Paid", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  mismatch: { label: "Under review", tone: "warning" },
};

export const PAYMENT_KIND: Record<PaymentKind, string> = {
  credit_package: "Credit package",
  subscription: "Plan",
  subscription_renewal: "Plan renewal",
};

/** What was actually charged, or the expected price while unpaid. Always USD-first. */
export function chargedAmount(payment: Payment): string {
  return formatMoney(payment.amount_paid ?? payment.price);
}

export function PaymentHistory({ payments }: { payments: Payment[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-subtle uppercase">
            <th scope="col" className="px-5 py-2.5 font-medium">Date</th>
            <th scope="col" className="px-3 py-2.5 font-medium">Item</th>
            <th scope="col" className="px-3 py-2.5 font-medium">Status</th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">Amount (USD)</th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">Credits</th>
            <th scope="col" className="px-5 py-2.5 font-medium"><span className="sr-only">Receipt</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {payments.map((p) => (
            <tr key={p.id}>
              <td className="px-5 py-3 whitespace-nowrap text-muted">{formatDate(p.paid_at ?? p.created_at, true)}</td>
              <td className="px-3 py-3 text-fg">{p.item_name} <span className="text-muted">· {PAYMENT_KIND[p.kind]}</span></td>
              <td className="px-3 py-3"><Badge tone={PAYMENT_STATUS[p.status].tone}>{PAYMENT_STATUS[p.status].label}</Badge></td>
              <td className="px-3 py-3 text-right font-mono tabular-nums">{chargedAmount(p)}</td>
              <td className="px-3 py-3 text-right font-mono tabular-nums text-muted">
                {p.credits ? (p.credits_granted ? `+${formatNumber(p.credits)}` : formatNumber(p.credits)) : "—"}
              </td>
              <td className="px-5 py-3 text-right">
                <Link className="text-accent hover:underline" href={`/app/billing/receipt/${p.id}`}>
                  {p.status === "succeeded" ? "Receipt" : "Details"}
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
