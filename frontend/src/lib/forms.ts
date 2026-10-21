import { ApiError } from "./api";

/** After showing errors, move keyboard focus to the first invalid field. */
export function focusFirstError(form: HTMLFormElement | null): void {
  requestAnimationFrame(() => {
    const el = form?.querySelector<HTMLElement>('[aria-invalid="true"]');
    el?.focus();
  });
}

/**
 * Split an API error into per-field messages and one general message.
 * `fields` lists the field names the form knows how to show.
 */
export function splitErrors(error: unknown, fields: string[]): { fieldErrors: Record<string, string>; formError: string | null } {
  if (!(error instanceof ApiError)) {
    return { fieldErrors: {}, formError: error instanceof Error ? error.message : "Something went wrong." };
  }
  const fieldErrors: Record<string, string> = {};
  const leftovers: string[] = [];
  for (const [name, message] of Object.entries(error.fieldErrors)) {
    if (fields.includes(name)) fieldErrors[name] = message;
    else leftovers.push(message);
  }
  if (error.code === "validation_error") {
    return { fieldErrors, formError: leftovers.length ? leftovers.join(" ") : Object.keys(fieldErrors).length ? null : error.message };
  }
  return { fieldErrors, formError: error.message };
}

/** Only allow redirects to paths on this site (prevents open redirects via ?next=). */
export function safeNextPath(next: string | null | undefined, fallback = "/app"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return fallback;
  return next;
}
