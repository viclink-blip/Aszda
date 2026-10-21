import type { Metadata } from "next";
import { Suspense } from "react";
import { SignInForm } from "@/components/auth/sign-in-form";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Sign in" };

export default function Page() {
  // Suspense is required because the form reads the URL's query string.
  return (
    <Suspense fallback={<PageSpinner />}>
      <SignInForm />
    </Suspense>
  );
}
