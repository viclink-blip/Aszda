import { useId } from "react";
import { cn } from "@/lib/cn";

export function Label({ className, ...rest }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("text-sm font-medium text-fg", className)} {...rest} />;
}

interface FieldProps {
  label: React.ReactNode;
  /** Shown under the control in red, and linked with aria-describedby. */
  error?: string | null;
  help?: React.ReactNode;
  required?: boolean;
  className?: string;
  /** Extra content on the right of the label, e.g. a character counter. */
  aside?: React.ReactNode;
  /**
   * Render prop receiving the props the control must spread:
   *   <Field label="Title">{(p) => <Input {...p} />}</Field>
   */
  children: (controlProps: {
    id: string;
    "aria-invalid"?: true;
    "aria-describedby"?: string;
    required?: boolean;
  }) => React.ReactNode;
}

/** Label + control + help text + error, wired up for screen readers. */
export function Field({ label, error, help, required, className, aside, children }: FieldProps) {
  const id = useId();
  const helpId = help ? `${id}-help` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [errorId, helpId].filter(Boolean).join(" ") || undefined;

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <div className="flex items-baseline justify-between gap-2">
        <Label htmlFor={id}>
          {label}
          {required && <span className="ml-0.5 text-accent" aria-hidden>*</span>}
        </Label>
        {aside}
      </div>
      {children({ id, "aria-invalid": error ? true : undefined, "aria-describedby": describedBy, required })}
      {help && !error && <p id={helpId} className="text-xs text-subtle">{help}</p>}
      {error && (
        <p id={errorId} className="text-xs font-medium text-danger" role="alert">
          {error}
        </p>
      )}
      {help && error && <p id={helpId} className="text-xs text-subtle">{help}</p>}
    </div>
  );
}

/** A form-level error (not tied to one field). */
export function FormError({ message, children }: { message?: string | null; children?: React.ReactNode }) {
  if (!message && !children) return null;
  return (
    <div role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-danger">
      {message}
      {children}
    </div>
  );
}
