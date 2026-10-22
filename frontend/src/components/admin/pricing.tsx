"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ErrorState } from "@/components/ui/error-state";
import { Field, FormError } from "@/components/ui/field";
import { Checkbox, Input } from "@/components/ui/input";
import { Notice } from "@/components/ui/notice";
import { LoadingRows } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { api, errorMessage } from "@/lib/api";
import { formatNumber, providerLabel } from "@/lib/format";
import type { AdminGenerationPrice, AdminPricing, AdminSaleItem } from "@/lib/types";

const usd = (value: number | null | undefined, digits = 2) =>
  value === null || value === undefined ? "—" : `$${value.toFixed(digits)}`;

function marginTone(percent: number | null): "success" | "warning" | "danger" | "neutral" {
  if (percent === null) return "neutral";
  return percent >= 50 ? "success" : percent >= 30 ? "warning" : "danger";
}

/** Admin: what each generation costs in credits, and what plans/packages give. USD prices are read-only. */
export function AdminPricingView() {
  const { data, error, reload, setData } = useApi(() => api.admin.pricing(), []);
  const [editModel, setEditModel] = useState<AdminGenerationPrice | null>(null);
  const [editItem, setEditItem] = useState<AdminSaleItem | null>(null);

  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return <LoadingRows rows={8} />;

  return (
    <>
      <Notice tone="info" className="mb-6" title="How this page works">
        Credit costs and allowances are set here; USD prices are fixed in billing_catalog.json and change only with
        the founder&apos;s approval. Changes apply to new jobs and purchases; running jobs keep the price they started
        with. Every change is recorded in the audit log.
      </Notice>

      <Card>
        <CardHeader title="Generation costs" description="Credits per 1,000 units of usage. Unpriced models cannot be used." />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[60rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-subtle uppercase">
                <th scope="col" className="px-5 py-2.5 font-medium">Model</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Status</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Credits per 1,000</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Typical jobs (credits · provider cost)</th>
                <th scope="col" className="px-5 py-2.5 font-medium"><span className="sr-only">Edit</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.generation.map((g) => (
                <tr key={`${g.provider}:${g.model}`} className="align-top">
                  <td className="px-5 py-3">
                    <p className="font-medium text-fg">{g.label}</p>
                    <p className="text-xs text-muted">{providerLabel(g.provider)} · {g.kind}</p>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-col items-start gap-1">
                      <Badge tone={g.price && g.enabled ? "success" : "warning"}>
                        {g.price && g.enabled ? `Priced (${g.source})` : g.source === null && g.price === null ? "Not priced" : "Disabled"}
                      </Badge>
                      <Badge tone={g.configured ? "success" : "neutral"}>{g.configured ? "Key set" : `No ${g.credential_env}`}</Badge>
                    </div>
                  </td>
                  <td className="px-3 py-3 font-mono text-xs">
                    {g.price ? Object.entries(g.price.credits_per_1000).map(([m, r]) => (
                      <div key={m}>{m}: {formatNumber(r)}</div>
                    )) : "—"}
                    {g.price && <div className="text-muted">min {g.price.minimum_credits}</div>}
                  </td>
                  <td className="px-3 py-3 text-xs">
                    {g.reference_jobs.map((j) => (
                      <div key={j.name} className="flex justify-between gap-4">
                        <span className="text-muted">{j.name}</span>
                        <span className="font-mono whitespace-nowrap">
                          {j.credits === null ? "—" : `${formatNumber(j.credits)} cr`} · {usd(j.provider_usd, 3)}
                        </span>
                      </div>
                    ))}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <Button size="sm" variant="outline" onClick={() => setEditModel(g)}>Edit</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {[{ title: "Plans (monthly credits)", items: data.plans }, { title: "Credit packages", items: data.credit_packages }].map((section) => (
        <Card key={section.title} className="mt-6">
          <CardHeader title={section.title}
            description={`Margin = (price − ${data.assumptions.payment_fee_percent}% card fee − maximum provider cost) ÷ (price − fee).`} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[52rem] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-subtle uppercase">
                  <th scope="col" className="px-5 py-2.5 font-medium">Item</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Price</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Credits</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Price per credit</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Max provider cost</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Worst-case margin</th>
                  {section.items[0]?.item_type === "plan" && <th scope="col" className="px-3 py-2.5 text-right font-medium">Monthly limit</th>}
                  <th scope="col" className="px-5 py-2.5 font-medium"><span className="sr-only">Edit</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {section.items.map((item) => (
                  <tr key={item.code}>
                    <td className="px-5 py-3 font-medium text-fg">{item.name}</td>
                    <td className="px-3 py-3 text-right font-mono">{item.price.formatted}</td>
                    <td className="px-3 py-3 text-right font-mono">{item.price.amount_minor === 0 ? "—" : item.credits === null ? "Not set" : formatNumber(item.credits)}</td>
                    <td className="px-3 py-3 text-right font-mono">{usd(item.usd_per_credit, 4)}</td>
                    <td className="px-3 py-3 text-right font-mono">{usd(item.max_provider_cost_usd)}</td>
                    <td className="px-3 py-3 text-right">
                      {item.gross_margin_percent === null ? "—" :
                        <Badge tone={marginTone(item.gross_margin_percent)}>{item.gross_margin_percent}%</Badge>}
                    </td>
                    {item.item_type === "plan" && (
                      <td className="px-3 py-3 text-right font-mono">
                        {item.price.amount_minor === 0 ? "—" : item.monthly_credit_limit ? formatNumber(item.monthly_credit_limit) : "Global"}
                      </td>
                    )}
                    <td className="px-5 py-3 text-right">
                      {item.price.amount_minor > 0 && (
                        <Button size="sm" variant="outline" onClick={() => setEditItem(item)}>Edit</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
      <p className="mt-4 text-xs text-subtle">{data.assumptions.explanation}</p>

      {editModel && <ModelDialog model={editModel} onClose={() => setEditModel(null)} onSaved={setData} />}
      {editItem && <ItemDialog item={editItem} onClose={() => setEditItem(null)} onSaved={setData} />}
    </>
  );
}

function numberOrNull(text: string): number | null {
  const value = text.trim() === "" ? NaN : Number(text);
  return Number.isFinite(value) ? value : null;
}

function ModelDialog({ model, onClose, onSaved }: {
  model: AdminGenerationPrice;
  onClose: () => void;
  onSaved: (data: AdminPricing) => void;
}) {
  const toast = useToast();
  const p = model.price;
  const [credits, setCredits] = useState<Record<string, string>>(
    Object.fromEntries(model.usage_metrics.map((m) => [m, p ? String(p.credits_per_1000[m] ?? "") : ""])));
  const [cost, setCost] = useState<Record<string, string>>(
    Object.fromEntries(model.usage_metrics.map((m) => [m, p?.provider_usd_per_1000?.[m] !== undefined ? String(p.provider_usd_per_1000[m]) : ""])));
  const [minimum, setMinimum] = useState(String(p?.minimum_credits ?? 1));
  const [source, setSource] = useState(p?.provider_price_source ?? "");
  const [enabled, setEnabled] = useState(model.enabled || !p);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    const rates: Record<string, number> = {};
    for (const metric of model.usage_metrics) {
      const value = numberOrNull(credits[metric]);
      if (value === null || value < 0) return setError(`Enter a credit rate for ${metric}.`);
      rates[metric] = value;
    }
    const costs: Record<string, number> = {};
    for (const metric of model.usage_metrics) {
      const value = numberOrNull(cost[metric]);
      if (value !== null) costs[metric] = value;
    }
    setBusy(true);
    setError(null);
    try {
      onSaved(await api.admin.setGenerationPrice(model.provider, model.model, {
        credits_per_1000: rates, minimum_credits: Math.max(1, Math.round(Number(minimum) || 1)),
        provider_usd_per_1000: Object.keys(costs).length ? costs : null,
        provider_price_source: source.trim() || null, enabled,
      }));
      toast.success("Price saved");
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()} title={`Credit cost: ${model.label}`}
      description="Rates are per 1,000 units (e.g. 32,000 per 1,000 video seconds = 32 credits per second)." size="lg">
      <form onSubmit={save} className="flex flex-col gap-4">
        {model.usage_metrics.map((metric) => (
          <div key={metric} className="grid gap-3 sm:grid-cols-2">
            <Field label={`Credits per 1,000 ${metric}`} required>
              {(props) => <Input {...props} inputMode="decimal" value={credits[metric]}
                onChange={(e) => setCredits({ ...credits, [metric]: e.target.value })} />}
            </Field>
            <Field label={`Provider USD per 1,000 ${metric}`} help="Optional, for margin reports.">
              {(props) => <Input {...props} inputMode="decimal" value={cost[metric]}
                onChange={(e) => setCost({ ...cost, [metric]: e.target.value })} />}
            </Field>
          </div>
        ))}
        <Field label="Minimum credits per job" required>
          {(props) => <Input {...props} inputMode="numeric" value={minimum} onChange={(e) => setMinimum(e.target.value)} />}
        </Field>
        <Field label="Where the provider price comes from" help="Link or note, so others can check it later.">
          {(props) => <Input {...props} value={source} maxLength={255} onChange={(e) => setSource(e.target.value)} />}
        </Field>
        <Checkbox label="Available for generation" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        <FormError message={error} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={busy}>Save</Button>
        </div>
      </form>
    </Dialog>
  );
}

function ItemDialog({ item, onClose, onSaved }: {
  item: AdminSaleItem;
  onClose: () => void;
  onSaved: (data: AdminPricing) => void;
}) {
  const toast = useToast();
  const isPlan = item.item_type === "plan";
  const [credits, setCredits] = useState(item.credits ? String(item.credits) : "");
  const [planCode, setPlanCode] = useState(item.paystack_plan_code ?? "");
  const [limit, setLimit] = useState(item.monthly_credit_limit ? String(item.monthly_credit_limit) : "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = isPlan
        ? { credits: numberOrNull(credits), paystack_plan_code: planCode.trim() || null, monthly_credit_limit: numberOrNull(limit) }
        : { credits: numberOrNull(credits) };
      onSaved(await api.admin.setBillingItem(item.item_type, item.code, body));
      toast.success("Saved");
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()} title={`${item.name} (${item.price.formatted}${isPlan ? "/month" : ""})`}
      description="The USD price cannot be changed here.">
      <form onSubmit={save} className="flex flex-col gap-4">
        <Field label={isPlan ? "Credits each month" : "Credits"} help="Leave empty to take it off sale.">
          {(props) => <Input {...props} inputMode="numeric" value={credits} onChange={(e) => setCredits(e.target.value)} />}
        </Field>
        {isPlan && (
          <>
            <Field label="Paystack plan code" help="PLN_… from the Paystack dashboard (a monthly USD plan with the same price).">
              {(props) => <Input {...props} value={planCode} onChange={(e) => setPlanCode(e.target.value)} />}
            </Field>
            <Field label="Monthly usage limit (credits)" help="Most a subscriber can spend per month, including bought credits. Empty = global limit.">
              {(props) => <Input {...props} inputMode="numeric" value={limit} onChange={(e) => setLimit(e.target.value)} />}
            </Field>
          </>
        )}
        <FormError message={error} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={busy}>Save</Button>
        </div>
      </form>
    </Dialog>
  );
}
