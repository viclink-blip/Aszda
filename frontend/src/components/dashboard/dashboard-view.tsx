"use client";

import { ArrowRight, Clapperboard, FolderKanban, History, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useCredits } from "@/components/app/credits-context";
import { JobItem } from "@/components/generation/job-item";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { ProjectRow } from "@/components/projects/project-card";
import { PlannedBadge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Stat } from "@/components/ui/stat";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatNumber } from "@/lib/format";
import { STUDIOS } from "@/lib/product";

export function DashboardView() {
  const { user } = useAuth();
  const { refresh: refreshCredits } = useCredits();
  const { data, error, loading, reload } = useApi(() => api.me.dashboard(), []);
  const [creating, setCreating] = useState(false);

  // Keep the header balance in step with the dashboard's numbers.
  useEffect(() => {
    if (data) void refreshCredits();
  }, [data, refreshCredits]);

  const firstName = (user?.display_name || "").split(" ")[0];

  return (
    <>
      <PageHeader
        title={firstName ? `Welcome, ${firstName}` : "Welcome"}
        description="Pick up a project, or start something new."
        actions={<Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" aria-hidden /> New project</Button>}
      />
      <CreateProjectDialog open={creating} onOpenChange={setCreating} />

      {error && !data ? (
        <ErrorState error={error} onRetry={reload} title="Could not load your dashboard" />
      ) : (
        <div className="flex flex-col gap-8">
          {/* Numbers straight from the API */}
          <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {loading && !data ? (
              Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-24" />)
            ) : data ? (
              <>
                <Stat label="Credits" value={formatNumber(data.credits.balance)} hint={<Link href="/app/credits" className="hover:text-fg">View ledger →</Link>} />
                <Stat label="Projects" value={formatNumber(data.counts.projects)} />
                <Stat label="Assets" value={formatNumber(data.counts.assets)} />
                <Stat label="Running now" value={formatNumber(data.counts.active_jobs)} hint="Generations in progress" />
              </>
            ) : null}
          </dl>

          {/* Studios */}
          <section aria-labelledby="studios-heading">
            <h2 id="studios-heading" className="mb-3 font-display text-base font-semibold text-fg">Studios</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {STUDIOS.map(({ slug, name, href, icon: Icon, provider }) => (
                <Link key={slug} href={href} className="group rounded-xl border border-line bg-surface p-4 transition-colors hover:border-line-strong">
                  <Icon className="h-5 w-5 text-accent" aria-hidden />
                  <p className="mt-3 font-medium text-fg">{name}</p>
                  <p className="mt-0.5 text-xs text-subtle">{provider}</p>
                </Link>
              ))}
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader
                title="Recent projects"
                action={<Link href="/app/projects" className="text-sm text-muted hover:text-fg">All projects</Link>}
              />
              {loading && !data ? (
                <div className="flex flex-col gap-2 p-5"><Skeleton className="h-12" /><Skeleton className="h-12" /></div>
              ) : data && data.recent_projects.length > 0 ? (
                <div className="divide-y divide-line">
                  {data.recent_projects.map((p) => <ProjectRow key={p.id} project={p} />)}
                </div>
              ) : (
                <EmptyState
                  className="m-5"
                  icon={FolderKanban}
                  title="No projects yet"
                  description="A project keeps one story's characters, scenes, assets and generations together."
                  action={<Button size="sm" onClick={() => setCreating(true)}><Plus className="h-4 w-4" aria-hidden /> Create your first project</Button>}
                />
              )}
            </Card>

            <Card>
              <CardHeader
                title="Recent generations"
                action={<Link href="/app/generations" className="text-sm text-muted hover:text-fg">All generations</Link>}
              />
              {loading && !data ? (
                <div className="flex flex-col gap-2 p-5"><Skeleton className="h-16" /><Skeleton className="h-16" /></div>
              ) : data && data.recent_jobs.length > 0 ? (
                <ul className="flex flex-col gap-2 p-3">
                  {data.recent_jobs.slice(0, 5).map((job) => <JobItem key={job.id} job={job} onRetried={() => void reload()} />)}
                </ul>
              ) : (
                <EmptyState
                  className="m-5"
                  icon={History}
                  title="Nothing generated yet"
                  description="When you generate a script, clip or voice-over, it appears here with its live status."
                  action={<ButtonLink href="/app/studio/script" size="sm" variant="outline">Open Script Studio</ButtonLink>}
                />
              )}
            </Card>
          </div>

          <Link href="/app/director" className="group flex flex-col gap-3 rounded-xl border border-dashed border-line-strong p-5 sm:flex-row sm:items-center">
            <Clapperboard className="h-6 w-6 shrink-0 text-muted" aria-hidden />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="font-medium text-fg">AI Film Director</p>
                <PlannedBadge />
              </div>
              <p className="mt-0.5 text-sm text-muted">A guided path from story to finished film. See what is planned and what you can use today.</p>
            </div>
            <ArrowRight className="h-4 w-4 text-subtle transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
        </div>
      )}
    </>
  );
}
