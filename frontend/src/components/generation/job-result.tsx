"use client";

import { Clapperboard, Download } from "lucide-react";
import { ButtonLink } from "@/components/ui/button";
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
    const history = (job.params.history ?? []) as { role: "user" | "assistant"; content: string }[];
    return (
      <div className="flex flex-col gap-3">
        {history.length > 0 && (
          <details className="rounded-lg border border-line bg-surface-2 p-3 text-sm">
            <summary className="cursor-pointer text-muted">Earlier in this conversation ({history.length / 2} {history.length === 2 ? "reply" : "replies"})</summary>
            <div className="mt-3 flex max-h-[40vh] flex-col gap-3 overflow-y-auto">
              {history.map((turn, i) => (
                <div key={i} className={turn.role === "user" ? "rounded-md bg-surface p-2 text-fg" : "text-muted"}>
                  <p className="mb-1 text-xs font-medium text-subtle">{turn.role === "user" ? "You" : "Claude"}</p>
                  {turn.role === "user" ? <p className="whitespace-pre-wrap">{turn.content}</p> : <SafeMarkdown text={turn.content} />}
                </div>
              ))}
            </div>
          </details>
        )}
        {history.length > 0 && typeof job.params.prompt === "string" && (
          <p className="rounded-md bg-surface-2 p-2 text-sm whitespace-pre-wrap text-fg"><span className="mb-1 block text-xs font-medium text-subtle">You</span>{job.params.prompt}</p>
        )}
        {result.truncated && (
          <Notice tone="warning">The text reached the maximum length you set and was cut off. Increase the maximum length and generate again for a complete result.</Notice>
        )}
        <div className="max-h-[60vh] overflow-y-auto rounded-lg border border-line bg-surface p-4">
          <SafeMarkdown text={result.text} />
        </div>
        {job.params.task !== "director_plan" && (
          <div>
            <ButtonLink size="sm" variant="secondary"
              href={`/app/director?from_job=${job.id}${job.project_id ? `&project=${job.project_id}` : ""}`}>
              <Clapperboard className="h-4 w-4" aria-hidden /> Send to AI Film Director
            </ButtonLink>
          </div>
        )}
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
