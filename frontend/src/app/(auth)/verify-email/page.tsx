import type { Metadata } from "next";
import { Suspense } from "react";
import { VerifyEmail } from "@/components/auth/verify-email";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Verify email" };

export default function Page() {
  // Suspense is required because the form reads the URL's query string.
  return (
    <Suspense fallback={<PageSpinner />}>
      <VerifyEmail />
    </Suspense>
  );
}
