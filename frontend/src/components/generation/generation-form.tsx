"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { useCredits } from "@/components/app/credits-context";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/ui/field";
import { Notice } from "@/components/ui/notice";
import { Skeleton } from "@/components/ui/skeleton";
import type { ModelOption } from "@/hooks/use-providers";
import { api, ApiError, errorMessage, newIdempotencyKey, type GenerationInput } from "@/lib/api";
import { focusFirstError } from "@/lib/forms";
import type { GenerationKind, Job } from "@/lib/types";
import { FieldControl } from "./field-control";
import { ModelPicker } from "./model-picker";
import { buildParams, checkRequired, type FormValues, initialValues, isFieldVisible } from "./params";
import { QuotePanel } from "./quote-panel";

interface GenerationFormProps {
  /** The `kind` sent to the API. */
  kind: GenerationKind;
  options: ModelOption[];
  loadingModels: boolean;
  projectId: string | null;
  sceneId?: string | null;
  /** Settings the studio fills in itself (not shown to the user). */
  fixedValues?: FormValues;
  /** Starting values that override the model defaults (e.g. a prompt from a scene). */
  initialOverrides?: FormValues;
  /** When set, submitting is blocked with this explanation (e.g. "Pick a character"). */
  blockedReason?: string | null;
  submitLabel: string;
  onCreated: (job: Job) => void;
}

/** Friendlier wording for errors people can act on. */
function submitErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "insufficient_credits":
        return "You do not have enough credits for this request. Payments are not active yet; contact ASZDA if you need more credits.";
      case "email_not_verified":
        return "Please confirm your email address first — use the banner at the top of the page to resend the link.";
      case "idempotency_key_reused":
        return "This looks like a changed duplicate of an earlier request. Please submit again.";
    }
  }
  return errorMessage(error);
}

export function GenerationForm({
  kind, options, loadingModels, projectId, sceneId = null, fixedValues = {}, initialOverrides = {},
  blockedReason = null, submitLabel, onCreated,
}: GenerationFormProps) {
  const { refresh: refreshCredits } = useCredits();
  const formRef = useRef<HTMLFormElement>(null);
  const [chosenKey, setChosenKey] = useState<string | null>(null);
  const [valuesByModel, setValuesByModel] = useState<Record<string, FormValues>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // One Idempotency-Key per submission; reused only when retrying the same request after a network error.
  const attempt = useRef<{ fingerprint: string; key: string } | null>(null);

  const available = options.filter((o) => o.model.available);
  const selected = options.find((o) => o.key === chosenKey) ?? available[0] ?? options[0] ?? null;
  const usable = Boolean(selected?.model.available);
  const hidden = new Set(Object.keys(fixedValues));
  const fields = selected?.model.fields ?? [];
  const values: FormValues = selected
    ? valuesByModel[selected.key] ?? { ...initialValues(fields), ...initialOverrides }
    : {};
  const merged = { ...values, ...fixedValues };

  const setValue = (name: string, value: unknown) => {
    if (!selected) return;
    setValuesByModel((all) => ({ ...all, [selected.key]: { ...values, [name]: value } }));
    setErrors((e) => {
      if (!e[name]) return e;
      const next = { ...e };
      delete next[name];
      return next;
    });
  };

  const clientErrors = selected ? checkRequired(fields, merged) : {};
  const request: GenerationInput | null = selected
    ? {
      provider: selected.provider.name,
      model: selected.model.id,
      kind,
      params: buildParams(fields, merged),
      project_id: projectId,
      scene_id: sceneId,
    }
    : null;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!request || !usable || blockedReason) return;
    setFormError(null);
    if (Object.keys(clientErrors).length) {
      setErrors(clientErrors);
      focusFirstError(formRef.current);
      return;
    }
    const fingerprint = JSON.stringify(request);
    if (!attempt.current || attempt.current.fingerprint !== fingerprint) {
      attempt.current = { fingerprint, key: newIdempotencyKey() };
    }
    setBusy(true);
    try {
      const { job } = await api.generation.create(request, attempt.current.key);
      attempt.current = null;
      setErrors({});
      onCreated(job);
      void refreshCredits();
    } catch (error) {
      // Keep the key only for network failures, where the server may have received the request.
      if (!(error instanceof ApiError && error.isNetworkError)) attempt.current = null;
      const fieldErrors = error instanceof ApiError ? error.fieldErrors : {};
      const known = Object.fromEntries(Object.entries(fieldErrors).filter(([name]) => fields.some((f) => f.name === name && !hidden.has(name))));
      setErrors(known);
      const rest = Object.entries(fieldErrors).filter(([name]) => !(name in known)).map(([, m]) => m);
      setFormError(Object.keys(known).length && !rest.length ? null : rest.length ? rest.join(" ") : submitErrorMessage(error));
      focusFirstError(formRef.current);
    } finally {
      setBusy(false);
    }
  };

  if (loadingModels) {
    return <div className="flex flex-col gap-3" role="status" aria-label="Loading models"><Skeleton className="h-20" /><Skeleton className="h-40" /></div>;
  }
  if (options.length === 0) {
    return <Notice tone="warning" title="No models for this studio">No provider offers this kind of generation yet.</Notice>;
  }

  return (
    <form ref={formRef} onSubmit={submit} noValidate className="flex flex-col gap-6">
      {available.length === 0 && (
        <Notice tone="warning" title="Generation is not available yet">
          None of the models for this studio can be used right now — each one is listed below with the reason.
          You can still look at the settings. Nothing will be generated or charged until a model is available.
        </Notice>
      )}
      <ModelPicker options={options} value={selected?.key ?? null} onChange={setChosenKey} />

      <fieldset disabled={!usable} className="flex flex-col gap-4 disabled:opacity-70">
        <legend className="mb-2 text-sm font-medium text-fg">Settings</legend>
        {fields
          .filter((field) => !hidden.has(field.name) && isFieldVisible(field, merged))
          .map((field) => (
            <FieldControl
              key={`${selected?.key}-${field.name}`}
              field={field}
              value={values[field.name]}
              onChange={(v) => setValue(field.name, v)}
              error={errors[field.name]}
              projectId={projectId}
            />
          ))}
      </fieldset>

      <QuotePanel request={request} enabled={usable && !blockedReason && Object.keys(clientErrors).length === 0} />

      <FormError message={formError}>
        {formError && formError.toLowerCase().includes("credits") && (
          <> <Link href="/app/credits" className="underline">See your credits</Link>.</>
        )}
      </FormError>
      {blockedReason && usable && <p className="text-sm text-muted">{blockedReason}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" size="lg" loading={busy} disabled={!usable || Boolean(blockedReason)}>
          <Sparkles className="h-4 w-4" aria-hidden /> {submitLabel}
        </Button>
        {!usable && <span className="text-sm text-muted">Unavailable — see the reason above.</span>}
      </div>
    </form>
  );
}
