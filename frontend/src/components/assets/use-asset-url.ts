"use client";

import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";

/**
 * Fetch a fresh, short-lived link for an asset each time it is shown.
 * (Links expire after a few minutes, so they are never stored.)
 */
export function useAssetUrl(assetId: string | null | undefined) {
  const [state, setState] = useState<{ id: string | null; url: string | null; error: string | null }>({
    id: null, url: null, error: null,
  });

  useEffect(() => {
    if (!assetId) return;
    let cancelled = false;
    api.assets.url(assetId)
      .then(({ url }) => !cancelled && setState({ id: assetId, url, error: null }))
      .catch((err) => !cancelled && setState({ id: assetId, url: null, error: errorMessage(err) }));
    return () => {
      cancelled = true;
    };
  }, [assetId]);

  // Ignore results that belong to a previous asset id.
  const current = state.id === assetId;
  return {
    url: current ? state.url : null,
    error: current ? state.error : null,
    loading: Boolean(assetId) && !current,
  };
}
