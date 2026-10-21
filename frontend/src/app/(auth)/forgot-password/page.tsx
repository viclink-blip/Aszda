import type { Metadata } from "next";
import { Suspense } from "react";
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Forgot password" };

export default function Page() {
  // Suspense is required because the form reads the URL's query string.
  return (
    <Suspense fallback={<PageSpinner />}>
      <ForgotPasswordForm />
    </Suspense>
  );
}
