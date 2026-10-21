import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./button";

/** Previous / next pager for API lists that use limit + offset. */
export function Pagination({ offset, limit, total, onChange }: {
  offset: number;
  limit: number;
  total: number;
  onChange: (offset: number) => void;
}) {
  if (total <= limit) return null;
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  return (
    <nav aria-label="Pages" className="mt-6 flex items-center justify-between gap-3">
      <p className="text-sm text-subtle">{from}–{to} of {total}</p>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
          <ChevronLeft className="h-4 w-4" aria-hidden /> Previous
        </Button>
        <Button size="sm" variant="outline" disabled={to >= total} onClick={() => onChange(offset + limit)}>
          Next <ChevronRight className="h-4 w-4" aria-hidden />
        </Button>
      </div>
    </nav>
  );
}
