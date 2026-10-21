import type { Metadata } from "next";
import { Suspense } from "react";
import { PaymentComplete } from "@/components/billing/payment-complete";
import { PageHeader } from "@/components/ui/page-header";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Payment" };

export default function PaymentCompletePage() {
  return (
    <>
      <PageHeader title="Payment" />
      <Suspense fallback={<PageSpinner />}>
        <PaymentComplete />
      </Suspense>
    </>
  );
}
