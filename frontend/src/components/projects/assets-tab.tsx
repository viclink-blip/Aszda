"use client";

import { FolderOpen } from "lucide-react";
import { useState } from "react";
import { AssetCard } from "@/components/assets/asset-card";
import { AssetMedia } from "@/components/assets/asset-media";
import { RenameAssetDialog } from "@/components/assets/rename-asset-dialog";
import { UploadButton } from "@/components/assets/upload-button";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Select } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { api, errorMessage } from "@/lib/api";
import type { Asset, AssetKind } from "@/lib/types";
import type { ProjectTabProps } from "./project-workspace";

const PAGE_SIZE = 24;

export function AssetsTab({ detail }: ProjectTabProps) {
  const projectId = detail.project.id;
  const toast = useToast();
  const [kind, setKind] = useState<AssetKind | "">("");
  const [offset, setOffset] = useState(0);
  const [preview, setPreview] = useState<Asset | null>(null);
  const [renaming, setRenaming] = useState<Asset | null>(null);
  const [deleting, setDeleting] = useState<Asset | null>(null);

  const { data, error, reload, setData } = useApi(
    () => api.projects.assets(projectId, { kind, limit: PAGE_SIZE, offset }),
    [projectId, kind, offset],
  );

  const replace = (asset: Asset) =>
    setData((d) => (d ? { ...d, items: d.items.map((a) => (a.id === asset.id ? asset : a)) } : d));

  const remove = async () => {
    if (!deleting) return;
    try {
      await api.assets.remove(deleting.id);
    } catch (err) {
      throw new Error(errorMessage(err));
    }
    toast.success("Asset deleted");
    await reload();
  };

  return (
    <section aria-labelledby="assets-heading">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="assets-heading" className="font-display text-lg font-semibold text-fg">Assets</h2>
          <p className="text-sm text-muted">Uploaded and generated files. Up to 50 MB per upload.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="w-36">
            <Select aria-label="Filter assets by type" value={kind} onChange={(e) => { setKind(e.target.value as AssetKind | ""); setOffset(0); }}>
              <option value="">All types</option>
              <option value="image">Images</option>
              <option value="video">Video</option>
              <option value="audio">Audio</option>
              <option value="text">Text</option>
            </Select>
          </div>
          <UploadButton projectId={projectId} multiple variant="primary" onUploaded={() => void reload()} />
        </div>
      </div>

      {error && !data ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-56" />)}
        </div>
      ) : data.items.length === 0 ? (
        <EmptyState
          icon={FolderOpen}
          title={kind ? "No assets of this type" : "No assets yet"}
          description="Upload images, video or audio, or generate them in a studio. Generated results land here automatically."
        />
      ) : (
        <>
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {data.items.map((asset) => (
              <AssetCard
                key={asset.id}
                asset={asset}
                onPreview={() => setPreview(asset)}
                onRename={() => setRenaming(asset)}
                onDelete={() => setDeleting(asset)}
              />
            ))}
          </ul>
          <Pagination offset={offset} limit={PAGE_SIZE} total={data.total} onChange={setOffset} />
        </>
      )}

      <Dialog open={preview !== null} onOpenChange={(open) => !open && setPreview(null)} title={preview?.display_name ?? ""} size="lg">
        {preview && <AssetMedia asset={preview} />}
      </Dialog>
      {renaming && <RenameAssetDialog asset={renaming} onClose={() => setRenaming(null)} onRenamed={replace} />}
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete asset?"
        description={<>Permanently delete <strong className="text-fg">{deleting?.display_name}</strong>? Characters or scenes using it will lose the reference.</>}
        confirmLabel="Delete"
        destructive
        onConfirm={remove}
      />
    </section>
  );
}
