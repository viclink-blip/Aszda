import { cn } from "@/lib/cn";

/** Progress bar. Pass value=null for "working, but we don't know how far". */
export function Progress({ value, label, className }: { value: number | null; label: string; className?: string }) {
  const known = value !== null && value !== undefined;
  const clamped = known ? Math.max(0, Math.min(100, value)) : 0;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={known ? clamped : undefined}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-3", className)}
    >
      {known ? (
        <div className="h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${clamped}%` }} />
      ) : (
        <div className="h-full w-2/5 rounded-full bg-accent/70 [animation:indeterminate_1.4s_ease-in-out_infinite]" />
      )}
    </div>
  );
}
