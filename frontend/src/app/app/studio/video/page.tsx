import type { Metadata } from "next";
import { Suspense } from "react";
import { StudioView } from "@/components/generation/studio-view";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Video Studio" };

export default function VideoStudioPage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <StudioView
        kind="video"
        title="Video Studio"
        description="Generate short clips with Runway: start from a text prompt, or from a reference image used as the first frame."
        submitLabel="Generate video"
        emptyText="Your clip will play here when it is ready. Video generation usually takes a few minutes."
      />
    </Suspense>
  );
}
