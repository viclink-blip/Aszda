"use client";

import { AlertTriangle } from "lucide-react";
import { errorMessage } from "@/lib/api";
import { Button } from "./button";

/** Shown when loading data failed, with a retry button. */
export function ErrorState({ error, onRetry, title = "Could not load this" }: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <div role="alert" className="flex flex-col items-center rounded-xl border border-danger/25 bg-danger-soft/50 px-6 py-10 text-center">
      <AlertTriangle className="h-6 w-6 text-danger" aria-hidden />
      <h3 className="mt-3 font-display font-semibold text-fg">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-muted">{errorMessage(error)}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
