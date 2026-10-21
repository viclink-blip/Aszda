"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Reminds unverified users to confirm their email (generation requires it). */
export function VerifyEmailBanner() {
  const { user } = useAuth();
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);
  if (!user || user.email_verified) return null;

  const resend = async () => {
    setState("sending");
    setError(null);
    try {
      await api.auth.resendVerification();
      setState("sent");
    } catch (err) {
      setError(errorMessage(err));
      setState("idle");
    }
  };

  return (
    <Notice
      tone="warning"
      title="Confirm your email address"
      className="mb-6"
      action={state !== "sent" && (
        <Button size="sm" variant="outline" onClick={resend} loading={state === "sending"}>Resend email</Button>
      )}
    >
      {state === "sent"
        ? <>We sent a new link to <strong>{user.email}</strong>. Open it to confirm.</>
        : <>We sent a link to <strong>{user.email}</strong>. Confirm it to keep your account recoverable — ASZDA asks for a confirmed email before generating.</>}
      {error && <span className="mt-1 block text-danger">{error}</span>}
    </Notice>
  );
}
