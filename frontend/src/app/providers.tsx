"use client";

import { ToastProvider } from "@/components/ui/toast";
import { AuthProvider } from "@/lib/auth";

/** Everything that needs to wrap the whole app on the client. */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ToastProvider>{children}</ToastProvider>
    </AuthProvider>
  );
}
