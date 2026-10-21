"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, FormError } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { focusFirstError, splitErrors } from "@/lib/forms";
import { AuthCard } from "./auth-card";
import { PasswordInput } from "./password-input";

export function SignUpForm() {
  const { signUp, status } = useAuth();
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const termsId = useId();
  const [form, setForm] = useState({ display_name: "", email: "", password: "" });
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [passwordProblems, setPasswordProblems] = useState<string[]>([]);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated" && !busy) router.replace("/app");
  }, [status, busy, router]);

  const update = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);
    setPasswordProblems([]);
    // Check the checkbox here too so the message is clear before any request.
    if (!accepted) {
      setFieldErrors({ accept_terms: "Please accept the Terms of Service and Privacy Policy to continue." });
      focusFirstError(formRef.current);
      return;
    }
    setFieldErrors({});
    setBusy(true);
    try {
      await signUp({ ...form, email: form.email.trim(), display_name: form.display_name.trim(), accept_terms: true });
      router.replace("/app");
    } catch (error) {
      const { fieldErrors: fe, formError: fm } = splitErrors(error, ["display_name", "email", "password", "accept_terms"]);
      if (error instanceof ApiError && error.code === "weak_password") {
        setPasswordProblems(error.problems);
        fe.password = error.message;
        setFormError(null);
      } else if (error instanceof ApiError && error.code === "email_taken") {
        fe.email = error.message;
        setFormError(null);
      } else {
        setFormError(fm);
      }
      setFieldErrors(fe);
      focusFirstError(formRef.current);
      setBusy(false);
    }
  };

  return (
    <AuthCard
      title="Create your account"
      description="Start a project and plan your first story in minutes."
      footer={<>Already have an account? <Link href="/sign-in" className="font-medium text-accent hover:underline">Sign in</Link></>}
    >
      <form ref={formRef} onSubmit={submit} noValidate className="flex flex-col gap-4">
        <FormError message={formError} />
        <Field label="Your name" error={fieldErrors.display_name} help="Shown in the studio. You can change it later.">
          {(p) => <Input {...p} autoComplete="name" maxLength={80} value={form.display_name} onChange={update("display_name")} required />}
        </Field>
        <Field label="Email" error={fieldErrors.email}>
          {(p) => <Input {...p} type="email" autoComplete="email" value={form.email} onChange={update("email")} required />}
        </Field>
        <Field label="Password" error={fieldErrors.password} help="At least 10 characters. Avoid repeating characters or using your email name.">
          {(p) => <PasswordInput {...p} autoComplete="new-password" maxLength={128} value={form.password} onChange={update("password")} required />}
        </Field>
        {passwordProblems.length > 0 && (
          <ul className="-mt-2 list-disc pl-5 text-xs text-danger">
            {passwordProblems.map((problem) => <li key={problem}>{problem}</li>)}
          </ul>
        )}
        <div className="flex flex-col gap-1.5">
          <label htmlFor={termsId} className="flex items-start gap-2.5 text-sm text-muted">
            <input
              id={termsId}
              type="checkbox"
              checked={accepted}
              onChange={(e) => setAccepted(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--accent)]"
              aria-invalid={fieldErrors.accept_terms ? true : undefined}
              aria-describedby={fieldErrors.accept_terms ? `${termsId}-error` : undefined}
            />
            <span>
              I agree to the <Link href="/terms" target="_blank" className="text-accent underline underline-offset-2">Terms of Service</Link> and{" "}
              <Link href="/privacy" target="_blank" className="text-accent underline underline-offset-2">Privacy Policy</Link>.
            </span>
          </label>
          {fieldErrors.accept_terms && (
            <p id={`${termsId}-error`} role="alert" className="text-xs font-medium text-danger">{fieldErrors.accept_terms}</p>
          )}
        </div>
        <Button type="submit" loading={busy} className="mt-2 w-full">Create account</Button>
      </form>
    </AuthCard>
  );
}
