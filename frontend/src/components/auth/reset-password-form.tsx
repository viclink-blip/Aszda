"use client";

import { CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import { Button, ButtonLink } from "@/components/ui/button";
import { Field, FormError } from "@/components/ui/field";
import { Notice } from "@/components/ui/notice";
import { api, ApiError } from "@/lib/api";
import { focusFirstError, splitErrors } from "@/lib/forms";
import { AuthCard } from "./auth-card";
import { PasswordInput } from "./password-input";

export function ResetPasswordForm() {
  const token = useSearchParams().get("token") ?? "";
  const formRef = useRef<HTMLFormElement>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [problems, setProblems] = useState<string[]>([]);
  const [formError, setFormError] = useState<string | null>(null);

  if (!token) {
    return (
      <AuthCard title="Reset link missing">
        <Notice tone="warning">This page needs the link from your password reset email. Request a new one below.</Notice>
        <ButtonLink href="/forgot-password" className="mt-4 w-full">Request a new link</ButtonLink>
      </AuthCard>
    );
  }

  if (done) {
    return (
      <AuthCard title="Password updated">
        <div className="flex gap-3 text-sm text-muted">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-success" aria-hidden />
          <p>Your password has been changed and other devices have been signed out. Sign in with your new password.</p>
        </div>
        <ButtonLink href="/sign-in" className="mt-5 w-full">Sign in</ButtonLink>
      </AuthCard>
    );
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);
    setProblems([]);
    if (password !== confirm) {
      setFieldErrors({ confirm: "The two passwords do not match." });
      focusFirstError(formRef.current);
      return;
    }
    setFieldErrors({});
    setBusy(true);
    try {
      await api.auth.confirmPasswordReset(token, password);
      setDone(true);
    } catch (error) {
      if (error instanceof ApiError && error.code === "weak_password") {
        setFieldErrors({ new_password: error.message });
        setProblems(error.problems);
      } else {
        const { fieldErrors: fe, formError: fm } = splitErrors(error, ["new_password"]);
        setFieldErrors(fe);
        setFormError(fm);
      }
      focusFirstError(formRef.current);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Choose a new password" footer={<Link href="/sign-in" className="font-medium text-accent hover:underline">Back to sign in</Link>}>
      <form ref={formRef} onSubmit={submit} noValidate className="flex flex-col gap-4">
        <FormError message={formError}>
          {formError && formError.includes("expired") && (
            <> <Link href="/forgot-password" className="underline">Request a new link</Link>.</>
          )}
        </FormError>
        <Field label="New password" error={fieldErrors.new_password} help="At least 10 characters.">
          {(p) => <PasswordInput {...p} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} required />}
        </Field>
        {problems.length > 0 && (
          <ul className="-mt-2 list-disc pl-5 text-xs text-danger">
            {problems.map((problem) => <li key={problem}>{problem}</li>)}
          </ul>
        )}
        <Field label="Repeat new password" error={fieldErrors.confirm}>
          {(p) => <PasswordInput {...p} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />}
        </Field>
        <Button type="submit" loading={busy} className="w-full">Update password</Button>
      </form>
    </AuthCard>
  );
}
