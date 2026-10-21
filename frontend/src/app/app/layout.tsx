"use client";

import { AppShell } from "@/components/app/app-shell";
import { CreditsProvider } from "@/components/app/credits-context";
import { RequireAuth } from "@/components/app/require-auth";

/** Everything under /app requires a signed-in user. */
export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <CreditsProvider>
        <AppShell>{children}</AppShell>
      </CreditsProvider>
    </RequireAuth>
  );
}
