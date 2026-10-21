import type { Metadata } from "next";
import { Suspense } from "react";
import { SignUpForm } from "@/components/auth/sign-up-form";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Create account" };

export default function Page() {
  // Suspense is required because the form reads the URL's query string.
  return (
    <Suspense fallback={<PageSpinner />}>
      <SignUpForm />
    </Suspense>
  );
}
