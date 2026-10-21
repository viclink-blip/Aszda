"use client";

import { Download } from "lucide-react";
import { AssetMedia } from "@/components/assets/asset-media";
import { useAssetUrl } from "@/components/assets/use-asset-url";
import { Notice } from "@/components/ui/notice";
import type { AssetKind, GenerationKind, Job } from "@/lib/types";
import { SafeMarkdown } from "./safe-markdown";

const ASSET_KIND_FOR_JOB: Record<GenerationKind, AssetKind> = {
  text: "text",
  image: "image",
  video: "video",
  animation: "video",
  speech: "audio",
};

function DownloadLink({ assetId }: { assetId: string }) {
  const { url } = useAssetUrl(assetId);
  if (!url) return null;
  return (
    <a href={url} download className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg">
      <Download className="h-4 w-4" aria-hidden /> Download
    </a>
  );
}

/** Shows what a completed job produced. */
export function JobResult({ job }: { job: Job }) {
  const result = job.result;
  if (!result) return <p className="text-sm text-muted">This job has no result.</p>;

  // Text jobs carry the text inline, so it can be shown without fetching the file.
  if (typeof result.text === "string") {
    return (
      <div className="flex flex-col gap-3">
        {result.truncated && (
          <Notice tone="warning">The text reached the maximum length you set and was cut off. Increase the maximum length and generate again for a complete result.</Notice>
        )}
        <div className="max-h-[60vh] overflow-y-auto rounded-lg border border-line bg-surface p-4">
          <SafeMarkdown text={result.text} />
        </div>
      </div>
    );
  }

  const ids = result.asset_ids ?? [];
  if (ids.length === 0) return <p className="text-sm text-muted">This job did not produce any files.</p>;
  const kind = ASSET_KIND_FOR_JOB[job.kind];
  return (
    <div className="flex flex-col gap-4">
      {ids.map((id, i) => (
        <div key={id} className="flex flex-col gap-2">
          <AssetMedia asset={{ id, kind, display_name: `Result ${i + 1}` }} />
          <DownloadLink assetId={id} />
        </div>
      ))}
    </div>
  );
}
