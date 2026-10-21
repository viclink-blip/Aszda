import { Loader2 } from "lucide-react";

/** Full-area loading indicator for page-level waits. */
export function PageSpinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center" role="status" aria-live="polite">
      <Loader2 className="h-6 w-6 animate-spin text-subtle" aria-hidden />
      <span className="sr-only">{label}…</span>
    </div>
  );
}
