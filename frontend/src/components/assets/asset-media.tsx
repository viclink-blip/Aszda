"use client";

import { AlertTriangle, FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { SafeMarkdown } from "@/components/generation/safe-markdown";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";
import type { Asset, AssetKind } from "@/lib/types";
import { useAssetUrl } from "./use-asset-url";

/** Loads a text file from its signed link and shows it safely. */
function TextFile({ url }: { url: string }) {
  const [text, setText] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    fetch(url)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
      .then((t) => !cancelled && setText(t))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [url]);
  if (failed) return <p className="text-sm text-danger">Could not load this text file.</p>;
  if (text === null) return <Skeleton className="h-24 w-full" />;
  return <SafeMarkdown text={text} />;
}

/**
 * Shows an asset: image, video player, audio player or text.
 * `compact` renders a small thumbnail (used in grids and pickers).
 */
export function AssetMedia({ asset, compact = false, className }: {
  asset: Pick<Asset, "id" | "kind" | "display_name">;
  compact?: boolean;
  className?: string;
}) {
  const { url, error, loading } = useAssetUrl(asset.id);

  if (loading) return <Skeleton className={cn(compact ? "aspect-video w-full" : "aspect-video w-full", className)} />;
  if (error || !url) {
    return (
      <div className={cn("flex aspect-video w-full flex-col items-center justify-center gap-1 rounded-lg bg-surface-2 p-3 text-center text-xs text-muted", className)}>
        <AlertTriangle className="h-4 w-4 text-warning" aria-hidden />
        {error ?? "Preview unavailable"}
      </div>
    );
  }

  return <MediaFor kind={asset.kind} url={url} name={asset.display_name} compact={compact} className={className} />;
}

function MediaFor({ kind, url, name, compact, className }: {
  kind: AssetKind; url: string; name: string; compact: boolean; className?: string;
}) {
  switch (kind) {
    case "image":
      // eslint-disable-next-line @next/next/no-img-element -- signed, short-lived URLs cannot go through next/image
      return <img src={url} alt={name} className={cn("w-full rounded-lg bg-surface-2 object-contain", compact ? "aspect-video object-cover" : "max-h-[70vh]", className)} />;
    case "video":
      return (
        <video
          src={url}
          controls={!compact}
          muted={compact}
          preload="metadata"
          playsInline
          className={cn("w-full rounded-lg bg-black", compact ? "aspect-video object-cover" : "max-h-[70vh]", className)}
          aria-label={name}
        />
      );
    case "audio":
      if (compact) {
        return (
          <div className={cn("flex aspect-video w-full items-center justify-center rounded-lg bg-surface-2", className)}>
            <audio src={url} controls preload="none" className="w-[90%]" aria-label={name} />
          </div>
        );
      }
      return <audio src={url} controls preload="metadata" className={cn("w-full", className)} aria-label={name} />;
    case "text":
      if (compact) {
        return (
          <div className={cn("flex aspect-video w-full items-center justify-center rounded-lg bg-surface-2 text-muted", className)}>
            <FileText className="h-6 w-6" aria-hidden />
          </div>
        );
      }
      return <div className={cn("max-h-[60vh] overflow-y-auto rounded-lg border border-line p-4", className)}><TextFile url={url} /></div>;
  }
}
