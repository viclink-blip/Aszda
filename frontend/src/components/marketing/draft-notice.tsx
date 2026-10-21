import { Notice } from "@/components/ui/notice";

/** Banner for legal pages that have not been reviewed by a lawyer yet. */
export function DraftNotice() {
  return (
    <Notice tone="warning" title="Draft — pending legal review" className="mb-8">
      This document is a working draft written in plain language. It has not yet been reviewed by a
      lawyer and may change before ASZDA Studio launches publicly.
    </Notice>
  );
}
