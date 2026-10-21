"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, FormError } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { focusFirstError, splitErrors } from "@/lib/forms";

export function ProfileForm() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const formRef = useRef<HTMLFormElement>(null);
  const [form, setForm] = useState({
    display_name: user?.display_name ?? "",
    preferred_language: user?.preferred_language ?? "",
    country: user?.country ?? "",
  });
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const country = form.country.trim().toUpperCase();
    const local: Record<string, string> = {};
    if (!form.display_name.trim()) local.display_name = "Your name cannot be empty.";
    if (country && !/^[A-Z]{2}$/.test(country)) local.country = "Use a two-letter country code, for example KE.";
    if (Object.keys(local).length) {
      setErrors(local);
      focusFirstError(formRef.current);
      return;
    }
    setBusy(true);
    setErrors({});
    setFormError(null);
    try {
      const { user: saved } = await api.me.update({
        display_name: form.display_name.trim(),
        preferred_language: form.preferred_language.trim() || null,
        country: country || null,
      });
      setUser(saved);
      toast.success("Profile saved");
    } catch (error) {
      const split = splitErrors(error, ["display_name", "preferred_language", "country"]);
      setErrors(split.fieldErrors);
      setFormError(split.formError);
      focusFirstError(formRef.current);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader title="Profile" description={user?.email} />
      <CardBody>
        <form ref={formRef} onSubmit={submit} noValidate className="flex flex-col gap-4">
          <FormError message={formError} />
          <Field label="Display name" required error={errors.display_name}>
            {(p) => <Input {...p} maxLength={80} value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />}
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Preferred language" error={errors.preferred_language} help="For example en, sw or fr.">
              {(p) => <Input {...p} maxLength={16} value={form.preferred_language} onChange={(e) => setForm({ ...form, preferred_language: e.target.value })} />}
            </Field>
            <Field label="Country" error={errors.country} help="Two-letter code, for example KE.">
              {(p) => <Input {...p} maxLength={2} autoComplete="country" value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} />}
            </Field>
          </div>
          <div className="flex justify-end">
            <Button type="submit" loading={busy}>Save profile</Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
