import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/money";
import type { PriceWithReference } from "@/lib/types";

/**
 * The one way prices are shown: the USD amount first and large, then the KES
 * amount small and explicitly labelled as a reference (it is never charged).
 */
export function PriceTag({ price, perMonth, size = "lg", className }: {
  price: PriceWithReference;
  perMonth?: boolean;
  size?: "lg" | "md";
  className?: string;
}) {
  return (
    <div className={className}>
      <p className="flex items-baseline gap-1">
        <span className={cn("font-display font-semibold text-fg tabular-nums",
          size === "lg" ? "text-4xl" : "text-2xl")}>
          {formatMoney(price)}
        </span>
        {perMonth && <span className="text-sm text-muted">/month</span>}
        <span className="ml-1 text-xs text-subtle">USD</span>
      </p>
      <ReferenceAmount price={price} perMonth={perMonth} />
    </div>
  );
}

export function ReferenceAmount({ price, perMonth, className }: {
  price: PriceWithReference;
  perMonth?: boolean;
  className?: string;
}) {
  return (
    <p className={cn("mt-1 text-xs text-subtle", className)} title={price.reference.label}>
      ≈ {formatMoney(price.reference)}{perMonth ? "/month" : ""}{" "}
      <span className="rounded border border-line px-1 py-px text-[10px] tracking-wide uppercase">reference</span>
    </p>
  );
}

const REASON_TEXT: Record<string, string> = {
  free_plan: "Included for everyone.",
  credits_not_configured: "Not on sale yet: the number of credits is still being decided.",
  paystack_plan_not_configured: "Not on sale yet: the monthly payment plan is being set up.",
};

export function unavailableItemText(reason: string | null): string {
  return (reason && REASON_TEXT[reason]) || "Not available yet.";
}
