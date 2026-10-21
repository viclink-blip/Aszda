"use client";

import { Check, ImageOff } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Asset } from "@/lib/types";
import { AssetMedia } from "./asset-media";
import { UploadButton } from "./upload-button";

/**
 * Choose one image: from the project's images, or upload a new one.
 * Without a project, the user's own library images are listed.
 */
export function AssetPicker({ projectId, value, onChange, label, allowNone = true, invalid = false }: {
  projectId: string | null;
  value: string | null;
  onChange: (assetId: string | null) => void;
  label: string;
  allowNone?: boolean;
  invalid?: boolean;
}) {
  const { data, loading, setData } = useApi(
    () => (projectId ? api.projects.assets(projectId, { kind: "image", limit: 100 }) : api.assets.list({ kind: "image", limit: 100 })),
    [projectId],
  );
  // Without a project, only show images that are not tied to some other project.
  const images = (data?.items ?? []).filter((a) => projectId || a.project_id === null);

  const added = (asset: Asset) => {
    if (asset.kind !== "image") return;
    setData((d) => (d ? { ...d, items: [asset, ...d.items], total: d.total + 1 } : d));
    onChange(asset.id);
  };

  return (
    <fieldset className={cn("rounded-lg border p-3", invalid ? "border-danger" : "border-line")}>
      <legend className="px-1 text-sm font-medium text-fg">{label}</legend>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-subtle">
          {projectId ? "Images in this project" : "Images in your library"} · PNG, JPEG or WebP work best
        </p>
        <UploadButton projectId={projectId} kind="image" size="sm" onUploaded={added} label="Upload image" />
      </div>
      {loading && !data ? (
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4"><Skeleton className="aspect-video" /><Skeleton className="aspect-video" /></div>
      ) : images.length === 0 ? (
        <div className="flex items-center gap-2 rounded-md bg-surface-2 px-3 py-4 text-sm text-muted">
          <ImageOff className="h-4 w-4" aria-hidden /> No images yet. Upload one to use it here.
        </div>
      ) : (
        <div role="radiogroup" aria-label={label} className="grid max-h-72 grid-cols-2 gap-2 overflow-y-auto sm:grid-cols-4">
          {allowNone && (
            <button
              type="button"
              role="radio"
              aria-checked={value === null}
              onClick={() => onChange(null)}
              className={cn(
                "flex aspect-video items-center justify-center rounded-lg border-2 text-xs text-muted",
                value === null ? "border-accent" : "border-dashed border-line-strong",
              )}
            >
              No image
            </button>
          )}
          {images.map((asset) => {
            const selected = value === asset.id;
            return (
              <button
                key={asset.id}
                type="button"
                role="radio"
                aria-checked={selected}
                aria-label={asset.display_name}
                onClick={() => onChange(asset.id)}
                className={cn("relative overflow-hidden rounded-lg border-2", selected ? "border-accent" : "border-transparent")}
              >
                <AssetMedia asset={asset} compact className="rounded-none" />
                {selected && (
                  <span className="absolute top-1 right-1 rounded-full bg-accent p-0.5 text-accent-fg"><Check className="h-3 w-3" aria-hidden /></span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </fieldset>
  );
}
