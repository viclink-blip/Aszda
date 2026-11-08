"use client";

import { ArrowRight, Clapperboard, FolderKanban, History, Plus, Sparkles, Wallet } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useCredits } from "@/components/app/credits-context";
import { JobItem } from "@/components/generation/job-item";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { ProjectRow } from "@/components/projects/project-card";
import { Button, ButtonLink } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatNumber } from "@/lib/format";

function MetricCard({
  label,
  value,
  description,
  icon: Icon,
  href,
}: {
  label: string;
  value: string;
  description: string;
  icon: typeof Wallet;
  href?: string;
}) {
  const content = (
    <div className="flex h-full min-h-32 flex-col justify-between rounded-2xl border border-line bg-surface p-5 transition-colors hover:border-line-strong">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-[0.12em] text-subtle">{label}</p>
        <Icon className="size-5 text-accent" aria-hidden />
      </div>
      <div>
        <p className="mt-4 font-display text-3xl font-semibold tracking-tight text-fg tabular-nums">{value}</p>
        <p className="mt-1 text-xs text-muted">{description}</p>
      </div>
    </div>
  );

  return href ? <Link href={href} className="block rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">{content}</Link> : content;
}

export function DashboardView() {
  const { user } = useAuth();
  const { refresh: refreshCredits } = useCredits();
  const { data, error, loading, reload } = useApi(() => api.me.dashboard(), []);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (data) void refreshCredits();
  }, [data, refreshCredits]);

  const firstName = (user?.display_name || "").trim().split(/\s+/)[0];
  const greeting = firstName ? `Welcome back, ${firstName}.` : "Welcome to ASZDA.";

  return (
    <>
      <CreateProjectDialog open={creating} onOpenChange={setCreating} />

      <div className="mx-auto flex w-full max-w-6xl flex-col gap-7">
        <section className="pt-1" aria-labelledby="dashboard-title">
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent">Your creative workspace</p>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="max-w-2xl">
              <h1 id="dashboard-title" className="font-display text-3xl font-semibold tracking-tight text-fg sm:text-4xl">
                {greeting} <span className="bg-gradient-to-r from-violet-400 to-sky-400 bg-clip-text text-transparent">What will you create?</span>
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-muted">
                Turn your idea into a cinematic story. ASZDA helps you shape the story, build its world and bring it to life.
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Button variant="outline" onClick={() => setCreating(true)}>
                <Plus className="size-4" aria-hidden /> New project
              </Button>
              <ButtonLink href="/app/director">
                <Sparkles className="size-4" aria-hidden /> Create a film
              </ButtonLink>
            </div>
          </div>
        </section>

        {error && !data ? (
          <ErrorState error={error} onRetry={reload} title="Could not load your workspace" />
        ) : (
          <>
            <section aria-label="Workspace overview" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {loading && !data ? (
                Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-32 rounded-2xl" />)
              ) : data ? (
                <>
                  <MetricCard
                    label="Available credits"
                    value={formatNumber(data.credits.balance)}
                    description="Your current creative balance"
                    icon={Wallet}
                    href="/app/credits"
                  />
                  <MetricCard
                    label="My projects"
                    value={formatNumber(data.counts.projects)}
                    description="Your saved creative projects"
                    icon={FolderKanban}
                    href="/app/projects"
                  />
                  <MetricCard
                    label="Creative assets"
                    value={formatNumber(data.counts.assets)}
                    description="Images, videos, audio and files"
                    icon={Sparkles}
                    href="/app/projects"
                  />
                  <MetricCard
                    label="Generations in progress"
                    value={formatNumber(data.counts.active_jobs)}
                    description="Jobs currently processing"
                    icon={History}
                    href="/app/generations"
                  />
                </>
              ) : null}
            </section>

            <section aria-labelledby="film-studio-heading" className="relative overflow-hidden rounded-3xl border border-violet-400/20 bg-gradient-to-br from-violet-950/60 via-surface to-surface p-6 sm:p-8">
              <div aria-hidden className="pointer-events-none absolute -right-16 -top-24 size-72 rounded-full bg-violet-500/15 blur-3xl" />
              <div className="relative flex flex-col items-start justify-between gap-7 sm:flex-row sm:items-center">
                <div className="max-w-xl">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-300">The Film Studio</p>
                  <h2 id="film-studio-heading" className="mt-3 max-w-lg font-display text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
                    Your next film starts with an idea.
                  </h2>
                  <p className="mt-3 max-w-lg text-sm leading-6 text-muted">
                    Start with your concept. Develop the story, shape characters, build scenes and guide the production from one creative workspace.
                  </p>
                  <ButtonLink href="/app/director" className="mt-5">
                    <Clapperboard className="size-4" aria-hidden /> Open Film Studio
                  </ButtonLink>
                </div>
                <div aria-hidden className="flex size-28 shrink-0 items-center justify-center self-center rounded-3xl bg-gradient-to-br from-violet-500 to-sky-600 shadow-lg shadow-violet-950/30 sm:size-36">
                  <Sparkles className="size-14 text-white sm:size-16" />
                </div>
              </div>
            </section>

            <section className="grid gap-5 lg:grid-cols-2">
              <div className="min-w-0 overflow-hidden rounded-2xl border border-line bg-surface">
                <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
                  <div>
                    <h2 className="font-display text-base font-semibold text-fg">Recent projects</h2>
                    <p className="mt-0.5 text-xs text-subtle">Continue where you left off.</p>
                  </div>
                  <ButtonLink href="/app/projects" variant="outline" size="sm">
                    View all <ArrowRight className="size-3.5" aria-hidden />
                  </ButtonLink>
                </div>
                {loading && !data ? (
                  <div className="flex flex-col gap-3 p-5"><Skeleton className="h-14" /><Skeleton className="h-14" /></div>
                ) : data && data.recent_projects.length > 0 ? (
                  <div className="divide-y divide-line">
                    {data.recent_projects.slice(0, 4).map((project) => <ProjectRow key={project.id} project={project} />)}
                  </div>
                ) : (
                  <EmptyState
                    className="m-5"
                    icon={FolderKanban}
                    title="Your first story starts here"
                    description="Create a project to keep its characters, scenes, assets and generations together."
                    action={<Button size="sm" onClick={() => setCreating(true)}><Plus className="size-4" aria-hidden /> Create a project</Button>}
                  />
                )}
              </div>

              <div className="min-w-0 overflow-hidden rounded-2xl border border-line bg-surface">
                <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
                  <div>
                    <h2 className="font-display text-base font-semibold text-fg">Recent activity</h2>
                    <p className="mt-0.5 text-xs text-subtle">Your latest AI generation jobs.</p>
                  </div>
                  <ButtonLink href="/app/generations" variant="outline" size="sm">
                    View history <ArrowRight className="size-3.5" aria-hidden />
                  </ButtonLink>
                </div>
                {loading && !data ? (
                  <div className="flex flex-col gap-3 p-5"><Skeleton className="h-16" /><Skeleton className="h-16" /></div>
                ) : data && data.recent_jobs.length > 0 ? (
                  <ul className="flex flex-col gap-2 p-3">
                    {data.recent_jobs.slice(0, 4).map((job) => <JobItem key={job.id} job={job} onRetried={() => void reload()} />)}
                  </ul>
                ) : (
                  <EmptyState
                    className="m-5"
                    icon={History}
                    title="No activity yet"
                    description="Your script, image, video and voice generations will appear here."
                    action={<ButtonLink href="/app/studio/script" size="sm" variant="outline">Open Story Studio</ButtonLink>}
                  />
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </>
  );
}
