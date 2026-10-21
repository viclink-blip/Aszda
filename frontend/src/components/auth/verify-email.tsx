"use client";

import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ButtonLink } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AuthCard } from "./auth-card";

type State = { kind: "working" } | { kind: "done" } | { kind: "error"; message: string };

export function VerifyEmail() {
  const token = useSearchParams().get("token") ?? "";
  const { status, user, setUser } = useAuth();
  const [state, setState] = useState<State>(token ? { kind: "working" } : { kind: "error", message: "This page needs the link from your verification email." });
  // A token works only once, so make sure we send it only once (React may run effects twice in development).
  const sent = useRef(false);

  useEffect(() => {
    if (!token || sent.current) return;
    sent.current = true;
    api.auth.verifyEmail(token)
      .then(({ user: verified }) => {
        setState({ kind: "done" });
        if (user && user.id === verified.id) setUser(verified);
      })
      .catch((error) => setState({ kind: "error", message: errorMessage(error) }));
  }, [token, user, setUser]);

  const next = status === "authenticated" ? "/app" : "/sign-in";

  if (state.kind === "working") {
    return (
      <AuthCard title="Confirming your email">
        <div className="flex items-center gap-3 text-sm text-muted" role="status">
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> One moment…
        </div>
      </AuthCard>
    );
  }
  if (state.kind === "done") {
    return (
      <AuthCard title="Email confirmed">
        <div className="flex gap-3 text-sm text-muted">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-success" aria-hidden />
          <p>Thank you — your email address is confirmed. You can now generate in every studio.</p>
        </div>
        <ButtonLink href={next} className="mt-5 w-full">{status === "authenticated" ? "Go to the studio" : "Sign in"}</ButtonLink>
      </AuthCard>
    );
  }
  return (
    <AuthCard title="Could not confirm your email">
      <div className="flex gap-3 text-sm text-muted">
        <XCircle className="h-5 w-5 shrink-0 text-danger" aria-hidden />
        <p>{state.message} You can ask for a new link from the banner on your dashboard.</p>
      </div>
      <ButtonLink href={next} className="mt-5 w-full">{status === "authenticated" ? "Go to the dashboard" : "Sign in"}</ButtonLink>
    </AuthCard>
  );
}
