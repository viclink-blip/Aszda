"use client";

import { Download, Eye, Pencil, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatBytes, formatDuration, formatRelative } from "@/lib/format";
import type { Asset } from "@/lib/types";
import { AssetMedia } from "./asset-media";
import { useAssetUrl } from "./use-asset-url";

function DownloadButton({ asset }: { asset: Asset }) {
  const { url } = useAssetUrl(asset.id);
  return (
    <a
      href={url ?? undefined}
      download={asset.display_name}
      aria-disabled={!url}
      className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg aria-disabled:pointer-events-none aria-disabled:opacity-50"
      aria-label={`Download ${asset.display_name}`}
    >
      <Download className="h-4 w-4" aria-hidden />
    </a>
  );
}

export function AssetCard({ asset, onPreview, onRename, onDelete }: {
  asset: Asset;
  onPreview: () => void;
  onRename: () => void;
  onDelete: () => void;
}) {
  const details = [
    formatBytes(asset.size_bytes),
    asset.duration_seconds ? formatDuration(asset.duration_seconds) : null,
    asset.width && asset.height ? `${asset.width}×${asset.height}` : null,
  ].filter(Boolean).join(" · ");

  return (
    <li className="flex flex-col overflow-hidden rounded-xl border border-line bg-surface">
      <button type="button" onClick={onPreview} className="block" aria-label={`Preview ${asset.display_name}`}>
        <AssetMedia asset={asset} compact className="pointer-events-none rounded-none" />
      </button>
      <div className="flex flex-1 flex-col gap-2 p-3">
        <p className="truncate text-sm font-medium text-fg" title={asset.display_name}>{asset.display_name}</p>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge>{asset.kind}</Badge>
          <Badge tone={asset.source === "generated" ? "accent" : "neutral"}>{asset.source === "generated" ? "Generated" : "Uploaded"}</Badge>
        </div>
        <p className="text-xs text-subtle">{details} · {formatRelative(asset.created_at)}</p>
        <div className="mt-auto flex items-center gap-1 pt-1">
          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={onPreview} aria-label={`Preview ${asset.display_name}`}>
            <Eye className="h-4 w-4" aria-hidden />
          </Button>
          <DownloadButton asset={asset} />
          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={onRename} aria-label={`Rename ${asset.display_name}`}>
            <Pencil className="h-4 w-4" aria-hidden />
          </Button>
          <Button size="icon" variant="ghost" className="ml-auto h-8 w-8" onClick={onDelete} aria-label={`Delete ${asset.display_name}`}>
            <Trash2 className="h-4 w-4" aria-hidden />
          </Button>
        </div>
      </div>
    </li>
  );
}
