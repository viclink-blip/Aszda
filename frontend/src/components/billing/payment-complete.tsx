"use client";

import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Notice } from "@/components/ui/notice";
import { PageSpinner } from "@/components/ui/spinner";
import { api, errorMessage } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { Payment } from "@/lib/types";
import { chargedAmount } from "./payment-history";

/**
 * Paystack sends the customer back here with ?reference=... The page asks OUR server to
 * verify the payment with Paystack; the redirect itself is never treated as proof of payment.
 */
export function PaymentComplete() {
  const params = useSearchParams();
  const reference = params.get("reference") || params.get("trxref") || "";
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const attempts = useRef(0);

  const check = async () => {
    if (!reference) return;
    setChecking(true);
    setError(null);
    try {
      const result = await api.billing.confirm(reference);
      setPayment(result.payment);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setChecking(false);
    }
  };

  // Check now, then a few more times while Paystack is still finishing.
  useEffect(() => {
    if (!reference) return;
    let timer: ReturnType<typeof setTimeout>;
    const run = async () => {
      attempts.current += 1;
      try {
        const result = await api.billing.confirm(reference);
        setPayment(result.payment);
        if (result.payment.status === "pending" && attempts.current < 5) timer = setTimeout(run, 3000);
      } catch (e) {
        setError(errorMessage(e));
      }
    };
    run();
    return () => clearTimeout(timer);
  }, [reference]);

  if (!reference) {
    return <Notice tone="warning" title="No payment reference">Open this page from the Paystack payment page.</Notice>;
  }

  return (
    <Card className="mx-auto max-w-lg">
      <CardBody className="flex flex-col items-center gap-3 py-10 text-center">
        {!payment && !error && <PageSpinner label="Confirming your payment with Paystack" />}
        {error && !payment && (
          <>
            <XCircle aria-hidden className="size-10 text-danger" />
            <p className="font-medium text-fg">We could not confirm the payment yet</p>
            <p className="text-sm text-muted">{error} If you paid, it will be confirmed automatically — you do not need to pay again.</p>
            <Button onClick={check} loading={checking}>Check again</Button>
          </>
        )}
        {payment?.status === "succeeded" && (
          <>
            <CheckCircle2 aria-hidden className="size-10 text-success" />
            <p className="font-display text-xl font-semibold text-fg">Payment received</p>
            <p className="text-muted">{payment.item_name} · {chargedAmount(payment)} USD</p>
            {payment.credits > 0 && <p className="text-sm text-fg">{formatNumber(payment.credits)} credits added to your account.</p>}
            <div className="mt-2 flex gap-2">
              <ButtonLink href={`/app/billing/receipt/${payment.id}`} variant="secondary">View receipt</ButtonLink>
              <ButtonLink href="/app">Back to the studio</ButtonLink>
            </div>
          </>
        )}
        {payment?.status === "pending" && (
          <>
            <Clock aria-hidden className="size-10 text-info" />
            <p className="font-medium text-fg">Payment not confirmed yet</p>
            <p className="text-sm text-muted">Paystack has not confirmed this payment. If you completed it, it will appear in Billing shortly.</p>
            <Button onClick={check} loading={checking}>Check again</Button>
          </>
        )}
        {payment?.status === "failed" && (
          <>
            <XCircle aria-hidden className="size-10 text-danger" />
            <p className="font-medium text-fg">The payment did not go through</p>
            <p className="text-sm text-muted">No credits were added. You can try again from Billing.</p>
            <ButtonLink href="/app/billing">Back to billing</ButtonLink>
          </>
        )}
        {payment?.status === "mismatch" && (
          <>
            <Clock aria-hidden className="size-10 text-warning" />
            <p className="font-medium text-fg">Your payment needs a manual check</p>
            <p className="text-sm text-muted">The amount Paystack reported did not match the price, so nothing was added automatically.
              ASZDA will review it; you do not need to pay again.</p>
            <ButtonLink href={`/app/billing/receipt/${payment.id}`} variant="secondary">View details</ButtonLink>
          </>
        )}
      </CardBody>
    </Card>
  );
}
