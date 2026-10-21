"use client";

import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Stat } from "@/components/ui/stat";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatNumber, JOB_STATUS_LABELS } from "@/lib/format";
import type { JobStatus } from "@/lib/types";

export function AdminOverview() {
  const { data, error, reload } = useApi(() => api.admin.overview(), []);
  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-24" />)}</div>;
  return (
    <div className="flex flex-col gap-8">
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Users" value={formatNumber(data.users.total)} hint={`${formatNumber(data.users.new)} new in ${data.period_days} days`} />
        <Stat label="Projects" value={formatNumber(data.projects)} />
        <Stat label="Credits charged" value={formatNumber(data.credits_charged)} hint={`Last ${data.period_days} days`} />
        <Stat label="Credits outstanding" value={formatNumber(data.credits_outstanding)} hint="Sum of all balances" />
      </dl>
      <section>
        <h2 className="mb-3 font-display text-base font-semibold text-fg">Jobs in the last {data.period_days} days</h2>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {(Object.keys(JOB_STATUS_LABELS) as JobStatus[]).map((s) => (
            <Stat key={s} label={JOB_STATUS_LABELS[s]} value={formatNumber(data.jobs[s] ?? 0)} />
          ))}
        </dl>
      </section>
    </div>
  );
}
