"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { Button } from "./button";
import { Field, FormError } from "./field";
import { Input } from "./input";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  /** Buttons shown at the bottom. */
  footer?: React.ReactNode;
  size?: "sm" | "md" | "lg";
}

/** Accessible modal (focus trap, Escape to close, labelled title) built on Radix. */
export function Dialog({ open, onOpenChange, title, description, children, footer, size = "md" }: DialogProps) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-[2px]" />
        <RadixDialog.Content
          className={cn(
            "fixed top-1/2 left-1/2 z-50 flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col",
            "rounded-xl border border-line bg-surface shadow-card focus:outline-none",
            size === "sm" && "max-w-md",
            size === "md" && "max-w-lg",
            size === "lg" && "max-w-2xl",
          )}
          // Radix expects aria-describedby={undefined} when a dialog has no description.
          {...(description ? {} : { "aria-describedby": undefined })}
        >
          <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
            <div>
              <RadixDialog.Title className="font-display text-lg font-semibold text-fg">{title}</RadixDialog.Title>
              {description ? (
                <RadixDialog.Description className="mt-1 text-sm text-muted">{description}</RadixDialog.Description>
              ) : null}
            </div>
            <RadixDialog.Close className="-mr-1 rounded-md p-1 text-subtle hover:bg-surface-2 hover:text-fg" aria-label="Close">
              <X className="h-5 w-5" aria-hidden />
            </RadixDialog.Close>
          </div>
          <div className="overflow-y-auto px-5 py-4">{children}</div>
          {footer && (
            <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>
          )}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: React.ReactNode;
  description: React.ReactNode;
  confirmLabel?: string;
  /** If set, the user must type this text before confirming (for destructive actions). */
  confirmText?: string;
  destructive?: boolean;
  onConfirm: () => Promise<void> | void;
}

/** "Are you sure?" dialog. Shows the error inline if the action fails. */
export function ConfirmDialog({
  open, onOpenChange, title, description, confirmLabel = "Confirm", confirmText, destructive, onConfirm,
}: ConfirmDialogProps) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const blocked = confirmText !== undefined && typed.trim() !== confirmText;

  const change = (next: boolean) => {
    if (!next) {
      setTyped("");
      setError(null);
    }
    onOpenChange(next);
  };

  const confirm = async (event: React.FormEvent) => {
    event.preventDefault();
    if (blocked) return;
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      change(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That did not work. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={change} title={title} size="sm">
      <form onSubmit={confirm} className="flex flex-col gap-4">
        <div className="text-sm text-muted">{description}</div>
        {confirmText !== undefined && (
          <Field label={<>Type <span className="font-mono text-fg">{confirmText}</span> to confirm</>}>
            {(p) => <Input {...p} value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" autoFocus />}
          </Field>
        )}
        <FormError message={error} />
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={() => change(false)}>Cancel</Button>
          <Button type="submit" variant={destructive ? "danger" : "primary"} loading={busy} disabled={blocked}>
            {confirmLabel}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
