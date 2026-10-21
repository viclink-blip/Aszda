"use client";

import { MailCheck } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, FormError } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { focusFirstError, splitErrors } from "@/lib/forms";
import { AuthCard } from "./auth-card";

export function ForgotPasswordForm() {
  const formRef = useRef<HTMLFormElement>(null);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setFieldError(null);
    setFormError(null);
    try {
      await api.auth.requestPasswordReset(email.trim());
      setSent(true);
    } catch (error) {
      const { fieldErrors, formError: fm } = splitErrors(error, ["email"]);
      setFieldError(fieldErrors.email ?? null);
      setFormError(fm);
      focusFirstError(formRef.current);
    } finally {
      setBusy(false);
    }
  };

  if (sent) {
    return (
      <AuthCard title="Check your email" footer={<Link href="/sign-in" className="font-medium text-accent hover:underline">Back to sign in</Link>}>
        <div className="flex gap-3 text-sm text-muted">
          <MailCheck className="h-5 w-5 shrink-0 text-success" aria-hidden />
          <p>
            If an account exists for <strong className="text-fg">{email}</strong>, we have sent a link to reset
            the password. The link expires after a short time.
          </p>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Reset your password"
      description="Enter your account email and we will send you a reset link."
      footer={<Link href="/sign-in" className="font-medium text-accent hover:underline">Back to sign in</Link>}
    >
      <form ref={formRef} onSubmit={submit} noValidate className="flex flex-col gap-4">
        <FormError message={formError} />
        <Field label="Email" error={fieldError}>
          {(p) => <Input {...p} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />}
        </Field>
        <Button type="submit" loading={busy} className="w-full">Send reset link</Button>
      </form>
    </AuthCard>
  );
}
