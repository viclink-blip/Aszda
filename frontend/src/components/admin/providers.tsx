"use client";

import { CheckCircle2, CircleAlert, PlugZap } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/dialog";
import { ErrorState } from "@/components/ui/error-state";
import { Notice } from "@/components/ui/notice";
import { LoadingRows } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { api, errorMessage } from "@/lib/api";
import { formatDate, formatNumber, providerLabel, unavailableText } from "@/lib/format";
import type { CapabilityRoute, ProviderHealth } from "@/lib/types";

const KIND_LABELS: Record<string, string> = { text: "Text", image: "Image", video: "Video", speech: "Voice", animation: "Animation" };

/** For each kind of work, which provider would run it now (and why not, if none). */
function RoutingCard({ routing }: { routing: CapabilityRoute[] }) {
  return (
    <Card>
      <CardHeader title="Routing" description="When a user does not pick a provider, ASZDA uses the configured one, then the listed fallbacks (ASZDA_AI_*_PROVIDER / _FALLBACKS)." />
      <ul className="divide-y divide-line">
        {routing.map((r) => (
          <li key={r.kind} className="grid gap-1 px-5 py-3 text-sm sm:grid-cols-[6rem_1fr_auto] sm:items-center">
            <span className="font-medium text-fg">{KIND_LABELS[r.kind]}</span>
            <span className="text-muted">
              Preferred: {r.preferred_provider ? providerLabel(r.preferred_provider) : "none"}
              {r.fallback_providers.length > 0 && <> · then {r.fallback_providers.map(providerLabel).join(", ")}</>}
              {r.problem?.details?.tried && (
                <span className="mt-1 block text-xs text-warning">
                  {r.problem.details.tried.map((t) => `${providerLabel(t.provider)}: ${t.message}`).join(" ")}
                </span>
              )}
            </span>
            {r.ready ? (
              <Badge tone={r.ready.fallback_used ? "warning" : "success"}>
                {providerLabel(r.ready.provider)} · {r.ready.model}{r.ready.fallback_used ? " (fallback)" : ""}
              </Badge>
            ) : (
              <Badge tone="warning">Not available</Badge>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function ProviderCard({ p, onTested }: { p: ProviderHealth; onTested: (p: ProviderHealth) => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const test = async (confirmCharge: boolean) => {
    setBusy(true);
    try {
      const { provider } = await api.admin.testProvider(p.name, confirmCharge);
      onTested(provider);
      if (provider.last_test?.ok) toast.success("Connection test passed");
      else toast.error("Connection test failed", provider.last_test?.last_error ?? undefined);
    } catch (err) {
      toast.error("Could not run the test", errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const last = p.last_test;
  return (
    <Card>
      <CardHeader
        title={p.label}
        description={p.capabilities.length ? `Offers: ${p.capabilities.map((k) => KIND_LABELS[k] ?? k).join(", ")}` : "No models configured yet"}
        action={
          <div className="flex flex-wrap gap-1.5">
            {!p.enabled && <Badge tone="warning">Switched off</Badge>}
            <Badge tone={p.settings_complete ? "success" : "warning"}>{p.settings_complete ? "Configured" : "Not configured"}</Badge>
          </div>
        }
      />
      <CardBody className="flex flex-col gap-4">
        {p.missing_settings.length > 0 && (
          <Notice tone="warning" title="Missing settings">
            Set these server environment variables, then restart the API and worker:{" "}
            {p.missing_settings.map((m, i) => <span key={m}>{i > 0 && ", "}<code className="font-mono text-fg">{m}</code></span>)}.
            Values are never shown here.
          </Notice>
        )}
        <div className="flex flex-col gap-2 text-sm sm:flex-row sm:items-start sm:justify-between">
          <div className="text-muted">
            <p className="flex items-center gap-1.5 text-fg">
              {last?.ok === true ? <CheckCircle2 className="size-4 text-success" aria-hidden /> :
                last?.ok === false ? <CircleAlert className="size-4 text-danger" aria-hidden /> :
                <PlugZap className="size-4 text-subtle" aria-hidden />}
              {last?.ok === true ? "Connection test passed" : last?.ok === false ? "Last connection test failed" : "Not tested yet"}
            </p>
            {last?.ok && last.result && <p className="mt-1 text-xs">{last.result}</p>}
            {last?.last_error && last.ok === false && <p className="mt-1 text-xs text-danger">{last.last_error}</p>}
            <p className="mt-1 text-xs text-subtle">
              Last success: {last?.last_success_at ? formatDate(last.last_success_at, true) : "never"}
              {last?.last_error_at && <> · Last error: {formatDate(last.last_error_at, true)}</>}
            </p>
            {p.connection_test.description && (
              <p className="mt-1 text-xs text-subtle">
                Test: {p.connection_test.description}{p.connection_test.may_charge && " This test may be charged by the provider."}
              </p>
            )}
          </div>
          {p.connection_test.available && (
            <Button size="sm" variant="secondary" loading={busy} disabled={!p.settings_complete}
              onClick={() => (p.connection_test.may_charge ? setConfirming(true) : test(false))}>
              Test connection
            </Button>
          )}
        </div>
      </CardBody>
      {p.models.length > 0 && (
        <ul className="divide-y divide-line border-t border-line">
          {p.models.map((m) => (
            <li key={m.id} className="flex flex-col gap-1 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium text-fg">
                  <span className="font-mono">{m.id}</span>{" "}
                  <span className="text-xs text-subtle">{KIND_LABELS[m.kind] ?? m.kind}{m.is_default && " · default"}</span>
                </p>
                {m.deprecated && <p className="text-xs text-warning">{m.deprecated}</p>}
                {!m.available && <p className="text-xs text-warning">{unavailableText(m.unavailable_reason)}</p>}
              </div>
              <div className="flex flex-wrap gap-1.5">
                <Badge tone={m.priced ? "success" : "warning"}>{m.priced ? "Priced" : "No price"}</Badge>
                <Badge tone={m.available ? "success" : "neutral"}>{m.available ? "Available" : "Unavailable"}</Badge>
              </div>
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog open={confirming} onOpenChange={setConfirming} title="Run a test that may be charged?"
        description="The provider may bill this connection test." confirmLabel="Run test"
        onConfirm={async () => { await test(true); }} />
    </Card>
  );
}

function CostsCard() {
  const { data, error, reload } = useApi(() => api.admin.providerCosts(30), []);
  if (error && !data) return <ErrorState error={error} onRetry={reload} title="Could not load provider costs" />;
  return (
    <Card>
      <CardHeader title="Provider costs (30 days)" description={data?.note} />
      {!data ? <div className="p-5"><LoadingRows rows={2} /></div> : data.rows.length === 0 ? (
        <CardBody className="text-sm text-muted">No provider costs recorded yet.</CardBody>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-subtle uppercase">
                <th scope="col" className="px-5 py-2.5 font-medium">Provider / model</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Outcome</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Jobs</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Credits charged</th>
                <th scope="col" className="px-5 py-2.5 text-right font-medium">Estimated cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.rows.map((r) => (
                <tr key={`${r.provider}-${r.model}-${r.outcome}-${r.absorbed_by_aszda}`}>
                  <td className="px-5 py-3"><span className="text-fg">{providerLabel(r.provider)}</span> <span className="font-mono text-xs text-subtle">{r.model}</span></td>
                  <td className="px-3 py-3">
                    <Badge tone={r.absorbed_by_aszda ? "warning" : "neutral"}>
                      {r.outcome === "safety_blocked" ? "Safety block (ASZDA pays)" : r.outcome === "completed" ? "Completed" : "Failed, billed"}
                    </Badge>
                  </td>
                  <td className="px-3 py-3 text-right font-mono tabular-nums">{formatNumber(r.jobs)}</td>
                  <td className="px-3 py-3 text-right font-mono tabular-nums">{formatNumber(r.credits_charged)}</td>
                  <td className="px-5 py-3 text-right font-mono tabular-nums text-muted">
                    {r.estimated_usd !== null ? `$${Number(r.estimated_usd).toFixed(2)}` : "no price entered"}
                    {r.estimated_usd !== null && r.jobs_with_estimate < r.jobs && <span className="block text-xs">({r.jobs_with_estimate} of {r.jobs} jobs)</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

/** Provider readiness and connection tests. API keys are never shown — only missing variable names. */
export function AdminProviders() {
  const { data, error, reload, setData } = useApi(() => api.admin.providerHealth(), []);
  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return <LoadingRows rows={4} />;
  const replace = (updated: ProviderHealth) =>
    setData({ ...data, providers: data.providers.map((p) => (p.name === updated.name ? updated : p)) });
  return (
    <div className="flex flex-col gap-6">
      <Notice tone="info">
        A provider is usable when its settings are complete, it is switched on, and each model has a credit price in
        Admin → Pricing. &ldquo;Configured&rdquo; does not mean a real generation has succeeded — use Test connection to
        check the credential (nothing is generated).
      </Notice>
      <RoutingCard routing={data.routing} />
      {data.providers.map((p) => <ProviderCard key={p.name} p={p} onTested={(u) => { replace(u); reload(); }} />)}
      <CostsCard />
    </div>
  );
}
