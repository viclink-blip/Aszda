"use client";

import { Coins } from "lucide-react";
import { useEffect, useState } from "react";
import { useDebounced } from "@/hooks/use-debounced";
import { api, ApiError, type GenerationInput } from "@/lib/api";
import { formatNumber } from "@/lib/format";

type QuoteState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; credits: number | null; balance: number; priced: boolean }
  | { kind: "incomplete"; message: string }
  | { kind: "error"; message: string };

/**
 * Asks the API what this request would cost (it validates without running it)
 * and shows the estimate next to the current balance.
 */
export function QuotePanel({ request, enabled }: { request: GenerationInput | null; enabled: boolean }) {
  const [state, setState] = useState<QuoteState>({ kind: "idle" });
  // Re-quote only after the settings stop changing for a moment.
  const key = useDebounced(enabled && request ? JSON.stringify(request) : "", 600);

  useEffect(() => {
    if (!key) return;
    let cancelled = false;
    const run = async () => {
      setState({ kind: "loading" });
      try {
        const quote = await api.generation.quote(JSON.parse(key) as GenerationInput);
        if (!cancelled) setState({ kind: "ready", credits: quote.estimated_credits, balance: quote.balance, priced: quote.priced });
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 422) {
          const first = Object.values(error.fieldErrors)[0];
          setState({ kind: "incomplete", message: first ?? error.message });
        } else {
          setState({ kind: "error", message: error instanceof Error ? error.message : "Could not estimate the cost." });
        }
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [key]);

  const shown: QuoteState = key ? state : { kind: "idle" };

  return (
    <div className="rounded-lg border border-line bg-surface-2/50 p-4" aria-live="polite">
      <div className="flex items-center gap-2 text-sm font-medium text-fg">
        <Coins className="h-4 w-4 text-accent" aria-hidden /> Estimated cost
      </div>
      <div className="mt-2 text-sm">
        {shown.kind === "idle" && <p className="text-muted">Choose an available model and fill in the settings to see an estimate.</p>}
        {shown.kind === "loading" && <p className="text-muted">Estimating…</p>}
        {shown.kind === "incomplete" && <p className="text-muted">Not ready to estimate yet: {shown.message}</p>}
        {shown.kind === "error" && <p className="text-danger">{shown.message}</p>}
        {shown.kind === "ready" && (
          shown.priced && shown.credits !== null ? (
            <>
              <p className="text-fg">
                Up to <strong className="font-display text-lg tabular-nums">{formatNumber(shown.credits)}</strong> credits
                <span className="text-muted"> · your balance: {formatNumber(shown.balance)}</span>
              </p>
              <p className="mt-1 text-xs text-subtle">
                These credits are reserved when you start. Any unused part is returned when the job finishes, and
                everything is refunded if it fails or you cancel.
              </p>
              {shown.balance < shown.credits && (
                <p className="mt-2 text-xs font-medium text-danger">Your balance is too low for this request.</p>
              )}
            </>
          ) : (
            <p className="text-muted">Pricing for this model has not been configured, so it cannot be used yet.</p>
          )
        )}
      </div>
    </div>
  );
}
