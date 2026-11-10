import type { Metadata } from "next";
import { Suspense } from "react";
import { StudioView } from "@/components/generation/studio-view";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Story Studio" };

export default function ScriptStudioPage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <StudioView
        kind="text"
        title="Story Studio"
        description="Shape your idea into a story. Write naturally and let ASZDA help develop your screenplay."
        submitLabel="Develop my story"
        emptyText="Your screenplay will appear here when it is ready."
      />
    </Suspense>
  );
}
