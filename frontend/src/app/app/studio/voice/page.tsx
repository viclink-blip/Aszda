import type { Metadata } from "next";
import { Suspense } from "react";
import { StudioView } from "@/components/generation/studio-view";
import { Notice } from "@/components/ui/notice";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Voice Studio" };

export default function VoiceStudioPage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <StudioView
        kind="speech"
        title="Voice Studio"
        description="Turn narration and dialogue into speech with OpenAI text-to-speech. Choose a voice, format and speed."
        notes={
          <Notice tone="info">
            The voices are AI-generated voices provided by OpenAI. Voice cloning (copying a real person&apos;s voice) is not offered.
          </Notice>
        }
        submitLabel="Create voice-over"
        emptyText="Write the text to speak. You can listen to and download the audio here."
      />
    </Suspense>
  );
}
