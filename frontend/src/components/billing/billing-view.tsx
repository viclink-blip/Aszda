"use client";

import { CreditCard, Receipt } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { LoadingRows } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { api, errorMessage } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import type { BillingPlan, CreditPackage, SubscriptionStatus } from "@/lib/types";
import { CurrencyNote, PackageCards, PlanCards } from "./catalog-sections";
import { PaymentHistory } from "./payment-history";
import { PriceTag } from "./price-tag";

const SUB_STATUS: Record<SubscriptionStatus, string> = {
  active: "Active",
  non_renewing: "Cancelled — ends at the end of the paid month",
  past_due: "Payment failed — please update your card with Paystack",
  cancelled: "Ended",
};

export function BillingView() {
  const toast = useToast();
  const overview = useApi(() => api.billing.overview(), []);
  const catalog = useApi(() => api.billing.catalog(), []);
  const [busy, setBusy] = useState<string | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);

  const error = overview.error || catalog.error;
  if (error && (!overview.data || !catalog.data)) {
    return (<><PageHeader title="Billing" /><ErrorState error={error} onRetry={() => { overview.reload(); catalog.reload(); }} /></>);
  }
  const data = overview.data;
  const checkout = data?.checkout ?? catalog.data?.checkout;
  const sub = data?.subscription;
  const activePlan = sub && sub.status !== "cancelled" ? sub.plan_code : "free";

  // Only an item code is sent; the server sets the price and currency, then we go to Paystack.
  const startCheckout = async (type: "credit_package" | "subscription", code: string) => {
    setBusy(`${type}:${code}`);
    try {
      const result = await api.billing.checkout(type, code);
      window.location.assign(result.authorization_url);
    } catch (e) {
      toast.error("Checkout could not start", errorMessage(e));
      setBusy(null);
    }
  };

  const planAction = (plan: BillingPlan) => {
    if (plan.code === activePlan) return null;
    if (plan.price.amount_minor === 0) return null;
    const blocked = !checkout?.enabled || !plan.purchasable || (sub && ["active", "past_due"].includes(sub.status));
    return (
      <Button className="w-full" disabled={!!blocked} loading={busy === `subscription:${plan.code}`}
        onClick={() => startCheckout("subscription", plan.code)}>
        Subscribe
      </Button>
    );
  };

  const packageAction = (pkg: CreditPackage) => (
    <Button className="w-full" variant="secondary" disabled={!checkout?.enabled || !pkg.purchasable}
      loading={busy === `credit_package:${pkg.code}`} onClick={() => startCheckout("credit_package", pkg.code)}>
      Buy for {pkg.price.formatted}
    </Button>
  );

  return (
    <>
      <PageHeader title="Billing" description="Your plan, credit purchases and receipts. Prices are in US dollars." />

      {checkout && !checkout.enabled && checkout.message && (
        <Notice tone="info" title="Checkout is not open yet" className="mb-6">{checkout.message}</Notice>
      )}
      {checkout?.enabled && checkout.mode === "test" && (
        <Notice tone="warning" title="Test mode" className="mb-6">
          Payments use Paystack test mode: no real money is taken. Use Paystack&apos;s test cards.
        </Notice>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader title="Current plan" />
          <CardBody>
            {!data ? <LoadingRows rows={2} /> : data.plan && sub && sub.status !== "cancelled" ? (
              <>
                <p className="font-display text-xl font-semibold text-fg">{data.plan.name}</p>
                <PriceTag className="mt-2" price={data.plan.price} perMonth size="md" />
                <p className="mt-3 text-sm text-muted">{SUB_STATUS[sub.status]}</p>
                {sub.current_period_end && (
                  <p className="text-sm text-muted">
                    {sub.status === "active" ? "Renews" : "Paid until"} {formatDate(sub.current_period_end)}
                  </p>
                )}
                {["active", "past_due"].includes(sub.status) && (
                  <Button variant="secondary" className="mt-4" onClick={() => setCancelOpen(true)}>Cancel plan</Button>
                )}
              </>
            ) : (
              <>
                <p className="font-display text-xl font-semibold text-fg">Free</p>
                <p className="mt-1 text-sm text-muted">No subscription. Choose a plan below when checkout opens.</p>
              </>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Credit balance" />
          <CardBody>
            <p className="font-display text-4xl font-semibold text-fg tabular-nums">
              {data ? formatNumber(data.credits.balance) : "…"}
            </p>
            <p className="mt-1 text-sm text-muted">credits</p>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="How you pay" />
          <CardBody className="text-sm text-muted">
            <p><CreditCard aria-hidden className="mr-1 inline size-4" />Payments are processed by Paystack.
              ASZDA never sees or stores your card details.</p>
            <p className="mt-2">You are charged in US dollars. KES amounts are a guide only.</p>
          </CardBody>
        </Card>
      </div>

      <h2 className="mt-10 mb-4 font-display text-xl font-semibold text-fg">Plans</h2>
      {catalog.data ? <PlanCards plans={catalog.data.plans} currentPlanCode={activePlan} action={planAction} />
        : <LoadingRows rows={3} />}

      <h2 className="mt-10 mb-4 font-display text-xl font-semibold text-fg">Buy extra credits</h2>
      {catalog.data ? <PackageCards packages={catalog.data.credit_packages} action={packageAction} />
        : <LoadingRows rows={2} />}

      <Card className="mt-10">
        <CardHeader title="Payment history" description="Receipts for every payment." />
        {!data ? <div className="p-5"><LoadingRows rows={3} /></div> : data.recent_payments.length === 0 ? (
          <EmptyState className="m-5" icon={Receipt} title="No payments yet"
            description="When you buy a plan or credits, the receipt appears here." />
        ) : <PaymentHistory payments={data.recent_payments} />}
      </Card>

      {catalog.data && <CurrencyNote currency={catalog.data.currency} className="mt-6" />}
      {sub && <p className="mt-2 text-xs text-subtle">Plan status: <Badge>{sub.status}</Badge></p>}

      <ConfirmDialog open={cancelOpen} onOpenChange={setCancelOpen} title="Cancel your plan?"
        description="Paystack will stop charging you. You keep your plan until the end of the month you paid for. Credits you already have stay in your account."
        confirmLabel="Cancel plan" destructive
        onConfirm={async () => {
          await api.billing.cancelSubscription();
          toast.success("Plan cancelled", "It will not renew.");
          await overview.reload();
        }} />
    </>
  );
}
