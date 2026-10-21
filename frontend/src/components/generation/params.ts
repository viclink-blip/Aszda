/**
 * Helpers that turn the provider's SettingField list into form values and
 * back into the `params` object the API expects.
 */

import type { SettingField } from "@/lib/types";

export type FormValues = Record<string, unknown>;

/** Is this field shown, given the other values? (show_when: {"mode": ["image_to_video"]}) */
export function isFieldVisible(field: SettingField, values: FormValues): boolean {
  if (!field.show_when) return true;
  return Object.entries(field.show_when).every(([other, allowed]) => allowed.includes(String(values[other] ?? "")));
}

/** Starting values: each field's default, as the form controls expect them. */
export function initialValues(fields: SettingField[]): FormValues {
  const values: FormValues = {};
  for (const field of fields) {
    if (field.default !== null && field.default !== undefined) {
      values[field.name] = field.type === "boolean" ? Boolean(field.default) : field.default;
    } else if (field.type === "boolean") {
      values[field.name] = false;
    }
  }
  return values;
}

/** A select whose every option is a whole number (e.g. "4", "6", "8") is sent as a number. */
function isNumericSelect(field: SettingField): boolean {
  return Boolean(field.options?.length) && field.options!.every((o) => /^-?\d+$/.test(o.value));
}

/**
 * Build the params for the API: only visible fields, empty values left out,
 * numbers converted from text inputs.
 */
export function buildParams(fields: SettingField[], values: FormValues): Record<string, unknown> {
  const params: Record<string, unknown> = {};
  for (const field of fields) {
    if (!isFieldVisible(field, values)) continue;
    const raw = values[field.name];
    if (raw === undefined || raw === null || raw === "") continue;
    switch (field.type) {
      case "integer": {
        const n = Number(raw);
        params[field.name] = Number.isFinite(n) ? Math.trunc(n) : raw;
        break;
      }
      case "number": {
        const n = Number(raw);
        params[field.name] = Number.isFinite(n) ? n : raw;
        break;
      }
      case "boolean":
        params[field.name] = Boolean(raw);
        break;
      case "select":
        params[field.name] = isNumericSelect(field) ? Number(raw) : raw;
        break;
      case "text":
      case "textarea": {
        const text = String(raw);
        if (text.trim() === "") continue;
        params[field.name] = text;
        break;
      }
      default:
        params[field.name] = raw;
    }
  }
  return params;
}

/** Simple checks before calling the API, so obvious mistakes are shown instantly. */
export function checkRequired(fields: SettingField[], values: FormValues): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const field of fields) {
    if (!isFieldVisible(field, values)) continue;
    const raw = values[field.name];
    const empty = raw === undefined || raw === null || (typeof raw === "string" && raw.trim() === "");
    if ((field.required || (field.type === "asset" && field.show_when)) && empty) {
      errors[field.name] = field.type === "asset" ? "Choose or upload an image." : `${field.label} is required.`;
      continue;
    }
    if (empty) continue;
    if (field.type === "integer" || field.type === "number") {
      const n = Number(raw);
      if (!Number.isFinite(n) || (field.type === "integer" && !Number.isInteger(n))) {
        errors[field.name] = field.type === "integer" ? "Enter a whole number." : "Enter a number.";
      } else if (field.minimum !== null && n < field.minimum) {
        errors[field.name] = `Must be at least ${field.minimum}.`;
      } else if (field.maximum !== null && n > field.maximum) {
        errors[field.name] = `Must be at most ${field.maximum}.`;
      }
    }
    if (field.max_length && typeof raw === "string" && raw.length > field.max_length) {
      errors[field.name] = `Use at most ${field.max_length} characters.`;
    }
  }
  return errors;
}
