import type { Metadata } from "next";
import { Suspense } from "react";
import { ResetPasswordForm } from "@/components/auth/reset-password-form";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Reset password" };

export default function Page() {
  // Suspense is required because the form reads the URL's query string.
  return (
    <Suspense fallback={<PageSpinner />}>
      <ResetPasswordForm />
    </Suspense>
  );
}
