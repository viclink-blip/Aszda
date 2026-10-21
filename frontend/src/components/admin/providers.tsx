"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingRows } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { unavailableText } from "@/lib/format";

/** Which providers are configured and priced. API keys are never shown — only the variable name. */
export function AdminProviders() {
  const { data, error, reload } = useApi(() => api.admin.providers(), []);
  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return <LoadingRows rows={3} />;
  return (
    <div className="flex flex-col gap-4">
      {data.providers.map((p) => (
        <Card key={p.name}>
          <CardHeader
            title={p.label}
            description={<>Credential environment variable: <code className="font-mono text-fg">{p.credential_env ?? "—"}</code></>}
            action={<Badge tone={p.configured ? "success" : "warning"}>{p.configured ? "Configured" : "Not configured"}</Badge>}
          />
          <ul className="divide-y divide-line">
            {p.models.map((m) => (
              <li key={m.id} className="flex flex-col gap-1 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-medium text-fg">{m.label} <span className="font-mono text-xs text-subtle">{m.id}</span></p>
                  {!m.available && <p className="text-xs text-warning">{unavailableText(m.unavailable_reason)}</p>}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <Badge tone={m.pricing ? "success" : "warning"}>{m.pricing ? "Priced" : "No price"}</Badge>
                  <Badge tone={m.available ? "success" : "neutral"}>{m.available ? "Available" : "Unavailable"}</Badge>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </div>
  );
}
