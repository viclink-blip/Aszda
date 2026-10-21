"use client";

import { ButtonLink } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Notice } from "@/components/ui/notice";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { CurrencyNote, PackageCards, PlanCards, PlanComparison } from "./catalog-sections";

/** The public pricing page body. Prices come from the API (billing_catalog.json), never from this file. */
export function PublicPricing() {
  const { data, error, reload } = useApi(() => api.billing.catalog(), []);

  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  if (!data) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-72 rounded-xl" />)}
      </div>
    );
  }

  return (
    <>
      {!data.checkout.enabled && data.checkout.message && (
        <Notice tone="info" title="Checkout is not open yet" className="mb-8">{data.checkout.message}</Notice>
      )}
      <h2 className="font-display text-2xl font-semibold text-fg">Monthly plans</h2>
      <p className="mt-1 mb-6 text-sm text-muted">Billed monthly in US dollars. Cancel any time.</p>
      <PlanCards plans={data.plans} action={(plan) => {
        const free = plan.price.amount_minor === 0;
        const buyable = data.checkout.enabled && plan.purchasable;
        if (!free && !buyable) return null; // the card explains why it is not on sale yet
        return (
          <ButtonLink href="/sign-up" variant={free ? "secondary" : "primary"} className="w-full">
            {free ? "Start free" : `Choose ${plan.name}`}
          </ButtonLink>
        );
      }} />

      <h2 className="mt-14 font-display text-2xl font-semibold text-fg">Compare plans</h2>
      <div className="mt-6"><PlanComparison plans={data.plans} /></div>

      <h2 className="mt-14 font-display text-2xl font-semibold text-fg">Extra credit packages</h2>
      <p className="mt-1 mb-6 text-sm text-muted">Top up any plan, including Free, with a one-off purchase.</p>
      <PackageCards packages={data.credit_packages} />

      <CurrencyNote currency={data.currency} className="mt-8" />
    </>
  );
}
