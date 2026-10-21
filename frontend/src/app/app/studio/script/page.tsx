import type { Metadata } from "next";
import { Suspense } from "react";
import { StudioView } from "@/components/generation/studio-view";
import { Notice } from "@/components/ui/notice";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Script Studio" };

export default function ScriptStudioPage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <StudioView
        kind="text"
        title="Script Studio"
        description="Develop a story concept, draft a script, outline characters or break your story into scenes — written by Anthropic Claude."
        notes={
          <Notice tone="info">
            The result is text you can copy into your storyboard. Turning it into scenes automatically is part of the
            planned AI Film Director.
          </Notice>
        }
        submitLabel="Write it"
        emptyText="Describe your idea and choose what you need. The text appears here when it is ready."
      />
    </Suspense>
  );
}
