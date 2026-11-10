"use client";

import {
  ArrowRight,
  Clapperboard,
  Film,
  FolderKanban,
  Image as ImageIcon,
  Plus,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useCredits } from "@/components/app/credits-context";
import { JobItem } from "@/components/generation/job-item";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { ProjectRow } from "@/components/projects/project-card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatNumber } from "@/lib/format";

const WORKFLOW = [
  { number: "01", title: "Shape the story", description: "Turn your idea into a screenplay.", href: "/app/studio/script", icon: Sparkles },
  { number: "02", title: "Build the film", description: "Plan characters and scenes.", href: "/app/director", icon: Clapperboard },
  { number: "03", title: "Create the visuals", description: "Generate images, video and voice.", href: "/app/director", icon: WandSparkles },
];

export function DashboardView() {
  const { user } = useAuth();
  const { refresh: refreshCredits } = useCredits();
  const { data, error, loading, reload } = useApi(() => api.me.dashboard(), []);
  const [creating, setCreating] = useState(false);
  const firstName = (user?.display_name || "").trim().split(" ")[0];

  useEffect(() => {
    if (data) void refreshCredits();
  }, [data, refreshCredits]);

  return (
    <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-8">
      <CreateProjectDialog open={creating} onOpenChange={setCreating} />

      <section>
        <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.22em] text-accent">Your creative workspace</div>
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-fg sm:text-[2.15rem]">
              Good morning{firstName ? `, ${firstName}` : ""}. <span className="text-brand">What will you create?</span>
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              Turn an idea into a cinematic story. ASZDA coordinates the creative process while you stay in control of the vision.
            </p>
          </div>
          <Button onClick={() => setCreating(true)} className="shrink-0">
            <Plus className="h-4 w-4" aria-hidden /> New project
          </Button>
        </div>
      </section>

      <section className="relative isolate overflow-hidden rounded-[22px] border border-[#514071] bg-[radial-gradient(ellipse_at_82%_12%,rgba(143,78,220,0.35),transparent_38%),linear-gradient(115deg,#1c172b,#111827_68%,#101b2b)] p-6 text-white shadow-[0_18px_55px_rgba(12,8,28,0.22)] sm:p-8">
        <div aria-hidden className="pointer-events-none absolute -right-10 -top-20 h-72 w-72 rounded-full border border-white/10 bg-[radial-gradient(circle,rgba(130,88,220,0.22),transparent_68%)]" />
        <div className="relative max-w-2xl">
          <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-[#c5a4ff]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#a879ff]" /> The film studio
          </div>
          <h2 className="mt-3 font-display text-3xl leading-tight font-semibold tracking-tight sm:text-[2.15rem]">
            Your next film starts<br className="hidden sm:block" /> with an <span className="bg-gradient-to-r from-[#dc9cff] to-[#68d1ff] bg-clip-text text-transparent">idea.</span>
          </h2>
          <p className="mt-3 max-w-xl text-sm leading-6 text-[#c2bfd2]">
            Describe the story you imagine. Develop the script, shape the characters, approve the scenes, then let ASZDA coordinate production.
          </p>
          <Link href="/app/director" className="mt-6 inline-flex h-11 items-center gap-2 rounded-lg bg-gradient-to-r from-[#884cff] to-[#397ff4] px-5 text-sm font-semibold text-white shadow-[0_8px_28px_rgba(103,72,206,0.35)] transition hover:-translate-y-0.5 hover:brightness-110">
            <Clapperboard className="h-4 w-4" aria-hidden /> Create a film <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        </div>
        <div aria-hidden className="absolute right-10 top-1/2 hidden h-36 w-36 -translate-y-1/2 rotate-12 items-center justify-center rounded-[30px] border border-white/15 bg-gradient-to-br from-[#7144a6]/80 to-[#176b94]/80 text-6xl shadow-2xl shadow-black/30 lg:flex">
          ✦
        </div>
      </section>

      {error && !data ? (
        <ErrorState error={error} onRetry={reload} title="Could not load your workspace" />
      ) : (
        <>
          <section aria-label="Workspace overview" className="grid gap-3 sm:grid-cols-3">
            {loading && !data ? (
              Array.from({ length: 3 }, (_, index) => <Skeleton key={index} className="h-28 rounded-2xl" />)
            ) : data ? (
              <>
                <OverviewCard icon={FolderKanban} label="Active projects" value={formatNumber(data.counts.projects)} detail="Your stories in progress" />
                <OverviewCard icon={ImageIcon} label="Creative assets" value={formatNumber(data.counts.assets)} detail="Images and files in your workspace" />
                <OverviewCard icon={Film} label="Running generations" value={formatNumber(data.counts.active_jobs)} detail="Production jobs in progress" />
              </>
            ) : null}
          </section>

          <section aria-labelledby="workflow-heading">
            <div className="mb-4 flex items-end justify-between gap-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-accent">Your creative process</p>
                <h2 id="workflow-heading" className="mt-1 font-display text-xl font-semibold text-fg">From imagination to screen</h2>
              </div>
              <Link href="/app/director" className="hidden items-center gap-1 text-xs font-medium text-muted transition hover:text-fg sm:inline-flex">Open Film Studio <ArrowRight className="h-3.5 w-3.5" aria-hidden /></Link>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              {WORKFLOW.map(({ number, title, description, href, icon: Icon }) => (
                <Link key={number} href={href} className="group rounded-2xl border border-line bg-surface p-5 transition duration-200 hover:-translate-y-0.5 hover:border-accent/50 hover:shadow-card">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs tracking-widest text-subtle">{number}</span>
                    <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent-soft text-accent"><Icon className="h-4 w-4" aria-hidden /></span>
                  </div>
                  <h3 className="mt-4 font-semibold text-fg">{title}</h3>
                  <p className="mt-1 text-sm leading-5 text-muted">{description}</p>
                  <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-accent">Open workspace <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" aria-hidden /></div>
                </Link>
              ))}
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="overflow-hidden rounded-2xl border border-line bg-surface">
              <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
                <div><h2 className="font-display text-base font-semibold text-fg">Recent projects</h2><p className="mt-0.5 text-xs text-muted">Continue where your creativity left off.</p></div>
                <Link href="/app/projects" className="text-xs font-semibold text-accent hover:underline">View all</Link>
              </div>
              {loading && !data ? (
                <div className="space-y-3 p-5"><Skeleton className="h-14" /><Skeleton className="h-14" /></div>
              ) : data && data.recent_projects.length > 0 ? (
                <div className="divide-y divide-line">{data.recent_projects.map((project) => <ProjectRow key={project.id} project={project} />)}</div>
              ) : (
                <EmptyState className="m-5" icon={FolderKanban} title="Your first story starts here" description="Create a project to keep its story, characters, scenes, assets and generations together." action={<Button size="sm" onClick={() => setCreating(true)}><Plus className="h-4 w-4" aria-hidden /> Create a project</Button>} />
              )}
            </div>

            <div className="overflow-hidden rounded-2xl border border-line bg-surface">
              <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
                <div><h2 className="font-display text-base font-semibold text-fg">Recent activity</h2><p className="mt-0.5 text-xs text-muted">Your latest creative generations.</p></div>
                <Link href="/app/generations" className="text-xs font-semibold text-accent hover:underline">Usage history</Link>
              </div>
              {loading && !data ? (
                <div className="space-y-3 p-5"><Skeleton className="h-14" /><Skeleton className="h-14" /></div>
              ) : data && data.recent_jobs.length > 0 ? (
                <ul className="flex flex-col gap-2 p-3">{data.recent_jobs.slice(0, 5).map((job) => <JobItem key={job.id} job={job} onRetried={() => void reload()} />)}</ul>
              ) : (
                <EmptyState className="m-5" icon={Film} title="Nothing generated yet" description="When you create a script, image, clip or voice-over, its status will appear here." />
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function OverviewCard({ icon: Icon, label, value, detail }: {
  icon: typeof FolderKanban;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted">{label}</p>
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent-soft text-accent"><Icon className="h-4 w-4" aria-hidden /></span>
      </div>
      <p className="mt-2 font-display text-3xl font-semibold tracking-tight text-fg tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-muted">{detail}</p>
    </div>
  );
}
