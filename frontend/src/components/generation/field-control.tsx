"use client";

import { AssetPicker } from "@/components/assets/asset-picker";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import type { SettingField } from "@/lib/types";

/** Renders one provider setting with the right control for its type. */
export function FieldControl({ field, value, onChange, error, projectId, disabled }: {
  field: SettingField;
  value: unknown;
  onChange: (value: unknown) => void;
  error?: string;
  projectId: string | null;
  disabled?: boolean;
}) {
  if (field.type === "asset") {
    return (
      <div className="flex flex-col gap-1.5">
        <AssetPicker
          projectId={projectId}
          label={field.label}
          value={(value as string | null) ?? null}
          onChange={(id) => onChange(id)}
          allowNone={false}
          invalid={Boolean(error)}
        />
        {field.help && <p className="text-xs text-subtle">{field.help}</p>}
        {error && <p className="text-xs font-medium text-danger" role="alert">{error}</p>}
      </div>
    );
  }

  if (field.type === "boolean") {
    return (
      <div className="flex flex-col gap-1">
        <label className="flex items-center gap-2.5 text-sm font-medium text-fg">
          <input
            type="checkbox"
            className="h-4 w-4 accent-[var(--accent)]"
            checked={Boolean(value)}
            disabled={disabled}
            onChange={(e) => onChange(e.target.checked)}
          />
          {field.label}
        </label>
        {field.help && <p className="pl-6.5 text-xs text-subtle">{field.help}</p>}
      </div>
    );
  }

  const text = value === undefined || value === null ? "" : String(value);
  const counter = field.max_length && (field.type === "textarea" || field.type === "text") ? (
    <span className={`text-xs tabular-nums ${text.length > field.max_length ? "text-danger" : "text-subtle"}`}>
      {text.length.toLocaleString()} / {field.max_length.toLocaleString()}
    </span>
  ) : undefined;

  const range = field.minimum !== null || field.maximum !== null
    ? `Between ${field.minimum ?? "…"} and ${field.maximum ?? "…"}.`
    : null;
  const help = [field.help, field.type === "integer" || field.type === "number" ? range : null].filter(Boolean).join(" ") || undefined;

  return (
    <Field label={field.label} required={field.required} error={error} help={help} aside={counter}>
      {(p) => {
        switch (field.type) {
          case "textarea":
            return <Textarea {...p} rows={field.name === "prompt" || field.name === "text" ? 6 : 3} value={text} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
          case "select":
            return (
              <Select {...p} value={text} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
                {!field.required && field.default === null && <option value="">Default</option>}
                {field.required && text === "" && <option value="" disabled>Choose…</option>}
                {field.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </Select>
            );
          case "integer":
          case "number":
            return (
              <Input
                {...p}
                type="number"
                inputMode={field.type === "integer" ? "numeric" : "decimal"}
                step={field.type === "integer" ? 1 : "any"}
                min={field.minimum ?? undefined}
                max={field.maximum ?? undefined}
                value={text}
                disabled={disabled}
                onChange={(e) => onChange(e.target.value)}
              />
            );
          default:
            return <Input {...p} value={text} disabled={disabled} maxLength={field.max_length ?? undefined} onChange={(e) => onChange(e.target.value)} />;
        }
      }}
    </Field>
  );
}
