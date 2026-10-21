import { cn } from "@/lib/cn";

/** A labelled number from the API. Shows "—" while unknown, never a made-up value. */
export function Stat({ label, value, hint, className }: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl border border-line bg-surface p-4", className)}>
      <dt className="text-xs font-medium tracking-wide text-subtle uppercase">{label}</dt>
      <dd className="mt-2 font-display text-2xl font-semibold tabular-nums text-fg">{value}</dd>
      {hint && <dd className="mt-1 text-xs text-muted">{hint}</dd>}
    </div>
  );
}
