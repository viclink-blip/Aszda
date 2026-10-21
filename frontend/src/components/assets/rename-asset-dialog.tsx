"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import type { Asset } from "@/lib/types";

export function RenameAssetDialog({ asset, onClose, onRenamed }: {
  asset: Asset;
  onClose: () => void;
  onRenamed: (asset: Asset) => void;
}) {
  const [name, setName] = useState(asset.display_name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setError("The name cannot be empty.");
      return;
    }
    setBusy(true);
    try {
      const { asset: saved } = await api.assets.rename(asset.id, name.trim());
      onRenamed(saved);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()} title="Rename asset" size="sm">
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Field label="Name" error={error}>
          {(p) => <Input {...p} value={name} maxLength={255} onChange={(e) => setName(e.target.value)} autoFocus />}
        </Field>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={busy}>Save</Button>
        </div>
      </form>
    </Dialog>
  );
}
