"use client";

import { Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import type { Asset } from "@/lib/types";

const ACCEPT_BY_KIND: Record<string, string> = {
  image: "image/png,image/jpeg,image/webp,image/gif",
  any: "image/png,image/jpeg,image/webp,image/gif,video/mp4,video/webm,video/quicktime,audio/mpeg,audio/wav,audio/ogg,audio/flac,audio/mp4",
};

/**
 * Pick one or more files and upload them (one after another).
 * The server checks the real file type, so `accept` is only a convenience.
 */
export function UploadButton({ projectId, kind = "any", multiple = false, onUploaded, label = "Upload", variant = "outline", size = "md" }: {
  projectId: string | null;
  kind?: "image" | "any";
  multiple?: boolean;
  onUploaded: (asset: Asset) => void;
  label?: string;
  variant?: "outline" | "primary";
  size?: "sm" | "md";
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const upload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setBusy(true);
    for (const file of Array.from(files)) {
      try {
        const { asset } = await api.assets.upload(file, projectId);
        if (kind === "image" && asset.kind !== "image") {
          toast.error("That file is not an image", `${file.name} was uploaded as ${asset.kind}. Choose a PNG, JPEG, WebP or GIF.`);
        } else {
          toast.success("Uploaded", asset.display_name);
        }
        onUploaded(asset);
      } catch (error) {
        toast.error(`Could not upload ${file.name}`, errorMessage(error));
      }
    }
    setBusy(false);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        accept={ACCEPT_BY_KIND[kind]}
        multiple={multiple}
        onChange={(e) => void upload(e.target.files)}
      />
      <Button variant={variant} size={size} loading={busy} onClick={() => inputRef.current?.click()}>
        {!busy && <Upload className="h-4 w-4" aria-hidden />} {busy ? "Uploading…" : label}
      </Button>
    </>
  );
}
