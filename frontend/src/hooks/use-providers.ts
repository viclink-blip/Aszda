"use client";

import { api } from "@/lib/api";
import type { GenerationKind, Provider, ProviderModel } from "@/lib/types";
import { useApi } from "./use-api";

/** A model together with the provider that offers it. */
export interface ModelOption {
  provider: Provider;
  model: ProviderModel;
  /** Unique key: "provider/model" */
  key: string;
}

/** Load /api/providers and return the models of one generation kind. */
export function useModels(kind: GenerationKind) {
  const state = useApi(() => api.generation.providers(), []);
  const options: ModelOption[] = [];
  for (const provider of state.data?.providers ?? []) {
    for (const model of provider.models) {
      if (model.kind === kind) options.push({ provider, model, key: `${provider.name}/${model.id}` });
    }
  }
  return { options, loading: state.loading, error: state.error, reload: state.reload };
}
