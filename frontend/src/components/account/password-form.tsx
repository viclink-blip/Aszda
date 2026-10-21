"use client";

import { useRef, useState } from "react";
import { PasswordInput } from "@/components/auth/password-input";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, FormError } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { focusFirstError, splitErrors } from "@/lib/forms";

export function PasswordForm() {
  const toast = useToast();
  const formRef = useRef<HTMLFormElement>(null);
  const [form, setForm] = useState({ current: "", next: "", repeat: "" });
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [problems, setProblems] = useState<string[]>([]);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);
    setProblems([]);
    if (form.next !== form.repeat) {
      setErrors({ repeat: "The two new passwords do not match." });
      focusFirstError(formRef.current);
      return;
    }
    setBusy(true);
    setErrors({});
    try {
      await api.me.changePassword(form.current, form.next);
      setForm({ current: "", next: "", repeat: "" });
      toast.success("Password changed", "Your other devices were signed out.");
    } catch (error) {
      if (error instanceof ApiError && error.code === "weak_password") {
        setErrors({ new_password: error.message });
        setProblems(error.problems);
      } else if (error instanceof ApiError && error.code === "invalid_password") {
        setErrors({ current_password: error.message });
      } else {
        const split = splitErrors(error, ["current_password", "new_password"]);
        setErrors(split.fieldErrors);
        setFormError(split.formError);
      }
      focusFirstError(formRef.current);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader title="Change password" description="Changing it signs out your other devices." />
      <CardBody>
        <form ref={formRef} onSubmit={submit} noValidate className="flex flex-col gap-4">
          <FormError message={formError} />
          <Field label="Current password" error={errors.current_password}>
            {(p) => <PasswordInput {...p} autoComplete="current-password" value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} />}
          </Field>
          <Field label="New password" error={errors.new_password} help="At least 10 characters.">
            {(p) => <PasswordInput {...p} autoComplete="new-password" value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} />}
          </Field>
          {problems.length > 0 && (
            <ul className="-mt-2 list-disc pl-5 text-xs text-danger">{problems.map((x) => <li key={x}>{x}</li>)}</ul>
          )}
          <Field label="Repeat new password" error={errors.repeat}>
            {(p) => <PasswordInput {...p} autoComplete="new-password" value={form.repeat} onChange={(e) => setForm({ ...form, repeat: e.target.value })} />}
          </Field>
          <div className="flex justify-end">
            <Button type="submit" loading={busy} disabled={!form.current || !form.next}>Change password</Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
