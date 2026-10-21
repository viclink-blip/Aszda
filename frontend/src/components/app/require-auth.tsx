"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { PageSpinner } from "@/components/ui/spinner";
import { useAuth } from "@/lib/auth";

/**
 * Client-side guard for /app/*. The API enforces access on every request;
 * this only decides what to show: a spinner while the session is restored,
 * or a redirect to sign-in when there is no session.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
  }, [status, pathname, router]);

  if (status !== "authenticated") return <PageSpinner label="Opening your studio" />;
  return <>{children}</>;
}

/** Only admins see admin pages (the API also refuses non-admins). */
export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "admin";

  useEffect(() => {
    if (user && !isAdmin) router.replace("/app");
  }, [user, isAdmin, router]);

  if (!isAdmin) return <PageSpinner />;
  return <>{children}</>;
}
