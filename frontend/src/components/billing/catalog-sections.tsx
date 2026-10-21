"use client";

import { Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/money";
import { formatNumber } from "@/lib/format";
import type { BillingPlan, CreditPackage, CurrencyInfo } from "@/lib/types";
import { PriceTag, unavailableItemText } from "./price-tag";

/** Renders the action area of a card: a button in the app, a link on the public site. */
export type ItemAction<T> = (item: T) => React.ReactNode;

export function PlanCards({ plans, currentPlanCode, action }: {
  plans: BillingPlan[];
  currentPlanCode?: string | null;
  action?: ItemAction<BillingPlan>;
}) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {plans.map((plan) => {
        const current = currentPlanCode !== undefined && (currentPlanCode ?? "free") === plan.code;
        return (
          <li key={plan.code}
            className={cn("flex flex-col rounded-xl border bg-surface p-5",
              current ? "border-accent" : "border-line")}>
            <div className="flex items-center justify-between gap-2">
              <h3 className="font-display text-lg font-semibold text-fg">{plan.name}</h3>
              {current && <Badge tone="accent">Your plan</Badge>}
            </div>
            <p className="mt-1 min-h-10 text-sm text-muted">{plan.summary}</p>
            <PriceTag className="mt-4" price={plan.price} perMonth />
            <p className="mt-3 text-sm text-fg">
              <Check aria-hidden className="mr-1 inline size-4 text-success" />
              {plan.monthly_credits ? `${formatNumber(plan.monthly_credits)} credits each month` :
                plan.price.amount_minor === 0 ? "Studio, projects and storyboards" : "Monthly credits: to be announced"}
            </p>
            <div className="mt-auto pt-5">
              {action ? action(plan) : null}
              {!plan.purchasable && plan.unavailable_reason !== "free_plan" && (
                <p className="mt-2 text-xs text-subtle">{unavailableItemText(plan.unavailable_reason)}</p>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function PackageCards({ packages, action }: {
  packages: CreditPackage[];
  action?: ItemAction<CreditPackage>;
}) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {packages.map((pkg) => (
        <li key={pkg.code} className="flex flex-col rounded-xl border border-line bg-surface p-5">
          <h3 className="font-display text-lg font-semibold text-fg">{pkg.name}</h3>
          <PriceTag className="mt-3" price={pkg.price} size="md" />
          <p className="mt-3 text-sm text-fg">
            {pkg.credits ? `${formatNumber(pkg.credits)} credits` : "Credits: to be announced"}
          </p>
          <p className="text-xs text-subtle">One-off purchase, no subscription.</p>
          <div className="mt-auto pt-5">
            {action ? action(pkg) : null}
            {!pkg.purchasable && <p className="mt-2 text-xs text-subtle">{unavailableItemText(pkg.unavailable_reason)}</p>}
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Side-by-side comparison of the plans. */
export function PlanComparison({ plans }: { plans: BillingPlan[] }) {
  const rows: { label: string; value: (p: BillingPlan) => React.ReactNode }[] = [
    { label: "Price (USD)", value: (p) => <span className="font-medium text-fg">{formatMoney(p.price)}/month</span> },
    { label: "KES reference", value: (p) => <span className="text-subtle">≈ {formatMoney(p.price.reference)}/month</span> },
    { label: "Monthly credits", value: (p) => p.monthly_credits ? formatNumber(p.monthly_credits) :
      p.price.amount_minor === 0 ? "—" : "To be announced" },
    { label: "Projects, characters, storyboards", value: () => <Check aria-label="Included" className="size-4 text-success" /> },
    { label: "Buy extra credit packages", value: () => "Yes" },
    { label: "Billing", value: (p) => p.price.amount_minor === 0 ? "Free" : "Monthly, cancel any time" },
  ];
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-surface">
      <table className="w-full min-w-[44rem] text-sm">
        <caption className="sr-only">Plan comparison</caption>
        <thead>
          <tr className="border-b border-line text-left">
            <th scope="col" className="px-5 py-3 font-medium text-subtle">Plan</th>
            {plans.map((p) => (
              <th key={p.code} scope="col" className="px-4 py-3 font-display font-semibold text-fg">{p.name}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row" className="px-5 py-3 text-left font-normal text-muted">{row.label}</th>
              {plans.map((p) => <td key={p.code} className="px-4 py-3 tabular-nums">{row.value(p)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The explanation shown wherever KES reference amounts appear. */
export function CurrencyNote({ currency, className }: { currency: CurrencyInfo; className?: string }) {
  return (
    <p className={cn("text-xs text-subtle", className)}>
      All prices are in US dollars (USD). {currency.reference_note}
    </p>
  );
}
