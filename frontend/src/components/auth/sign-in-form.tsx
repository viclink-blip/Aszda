"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, FormError } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";
import { focusFirstError, safeNextPath, splitErrors } from "@/lib/forms";
import { AuthCard } from "./auth-card";
import { PasswordInput } from "./password-input";

export function SignInForm() {
  const { signIn, status } = useAuth();
  const router = useRouter();
  const next = safeNextPath(useSearchParams().get("next"));
  const formRef = useRef<HTMLFormElement>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  // Already signed in (e.g. came back with the browser button): go straight to the app.
  useEffect(() => {
    if (status === "authenticated") router.replace(next);
  }, [status, next, router]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    setFieldErrors({});
    try {
      await signIn(email.trim(), password);
      router.replace(next);
    } catch (error) {
      const { fieldErrors: fe, formError: fm } = splitErrors(error, ["email", "password"]);
      setFieldErrors(fe);
      setFormError(fm);
      focusFirstError(formRef.current);
      setBusy(false);
    }
  };

  return (
    <AuthCard
      title="Welcome back"
      description="Sign in to continue to ASZDA Studio."
      footer={<>New to ASZDA? <Link href="/sign-up" className="font-medium text-accent hover:underline">Create an account</Link></>}
    >
      <form ref={formRef} onSubmit={submit} noValidate className="flex flex-col gap-4">
        <FormError message={formError} />
        <Field label="Email" error={fieldErrors.email}>
          {(p) => <Input {...p} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />}
        </Field>
        <Field
          label="Password"
          error={fieldErrors.password}
          aside={<Link href="/forgot-password" className="text-xs text-muted hover:text-fg">Forgot password?</Link>}
        >
          {(p) => <PasswordInput {...p} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />}
        </Field>
        <Button type="submit" loading={busy} className="mt-2 w-full">Sign in</Button>
      </form>
    </AuthCard>
  );
}
