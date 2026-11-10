"use client";

import { Clapperboard, Film, FolderKanban, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useCredits } from "@/components/app/credits-context";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatNumber, PROJECT_STATUS_LABELS } from "@/lib/format";

export function DashboardView() {
  const { refresh: refreshCredits } = useCredits();
  const { data, error, loading, reload } = useApi(() => api.me.dashboard(), []);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (data) void refreshCredits();
  }, [data, refreshCredits]);

  const counts = data?.counts;

  return (
    <div className="mx-auto flex w-full max-w-[1180px] flex-col">
      <CreateProjectDialog open={creating} onOpenChange={setCreating} />

      <section>
        <div className="text-[10px] font-extrabold uppercase tracking-[2px] text-[#b78aff]">Your creative workspace</div>
        <h1 className="mt-2 text-[27px] leading-tight tracking-[-1px] text-[#f4f5fb] sm:text-[32px]">
          Good morning. <span className="bg-gradient-to-r from-[#d58bff] to-[#67cfff] bg-clip-text text-transparent">What will you create?</span>
        </h1>
        <p className="mb-[25px] mt-2 max-w-[680px] text-sm leading-6 text-[#9ba1b5]">
          Turn an idea into a cinematic story. ASZDA coordinates the creative process while you stay in control of the vision.
        </p>
      </section>

      <section className="flex items-center justify-between gap-6 rounded-[20px] border border-[#38314f] bg-[radial-gradient(ellipse_at_90%_10%,#54328a66,transparent_40%),linear-gradient(120deg,#1b172a,#111522)] p-6 sm:p-7">
        <div className="min-w-0">
          <div className="text-[10px] font-extrabold uppercase tracking-[2px] text-[#b78aff]">The film studio</div>
          <h2 className="mt-2 text-2xl leading-tight font-semibold text-white sm:text-[26px]">
            Your next film starts<br />with an <span className="bg-gradient-to-r from-[#d58bff] to-[#67cfff] bg-clip-text text-transparent">idea.</span>
          </h2>
          <p className="mt-2 max-w-[530px] text-sm leading-6 text-[#b2b4c7]">
            Describe the story you imagine. Develop the script, shape the characters, approve the scenes, then let ASZDA coordinate production.
          </p>
          <Link href="/app/director" className="mt-4 inline-flex items-center gap-2 rounded-[10px] bg-gradient-to-r from-[#884cff] to-[#397ff4] px-[17px] py-[11px] text-sm font-bold text-white shadow-[0_7px_24px_#6748ce33] transition hover:-translate-y-px hover:brightness-110">
            <Plus className="h-4 w-4" aria-hidden /> Create a film
          </Link>
        </div>
        <div aria-hidden className="hidden h-[150px] w-[190px] shrink-0 items-center justify-center rounded-[18px] bg-gradient-to-br from-[#6e3d9e] to-[#176b94] text-[58px] shadow-2xl shadow-black/50 lg:flex">✦</div>
      </section>

      {error && !data ? (
        <div className="mt-6"><ErrorState error={error} onRetry={reload} title="Could not load your workspace" /></div>
      ) : (
        <>
          <section aria-label="Workspace overview" className="my-[22px] grid gap-4 sm:grid-cols-3">
            {loading && !data ? (
              Array.from({ length: 3 }, (_, index) => <Skeleton key={index} className="h-[112px] rounded-2xl" />)
            ) : counts ? (
              <>
                <OverviewCard label="Active projects" value={formatNumber(counts.active_projects)} detail="Your stories in progress" />
                <OverviewCard label="Characters" value={formatNumber(counts.characters)} detail="Saved in your creative library" />
                <OverviewCard label="Films created" value={formatNumber(counts.films)} detail="Your completed productions" />
              </>
            ) : null}
          </section>

          <div className="mb-3 mt-7 flex items-center justify-between gap-4">
            <h2 className="text-[17px] font-semibold text-[#f4f5fb]">Recent projects</h2>
            <Link href="/app/projects" className="rounded-[10px] border border-[#292d3d] bg-transparent px-3 py-2 text-xs font-semibold text-[#c8ccda] hover:bg-[#191c29]">View all projects</Link>
          </div>

          {loading && !data ? (
            <div className="space-y-3"><Skeleton className="h-[86px] rounded-xl" /><Skeleton className="h-[86px] rounded-xl" /></div>
          ) : data && data.recent_projects.length > 0 ? (
            <div className="divide-y divide-[#292d3d]">
              {data.recent_projects.map((project) => (
                <Link key={project.id} href={`/app/projects/${project.id}`} className="flex items-center gap-3 py-3.5 transition hover:bg-white/[0.02] sm:gap-4">
                  <div className="grid h-[58px] w-[90px] shrink-0 place-items-center rounded-[9px] bg-gradient-to-br from-[#38285c] to-[#172d48] text-[21px]">🎬</div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-semibold text-[#f4f5fb]">{project.title}</div>
                    <div className="mt-1 truncate text-xs text-[#9ba1b5]">{project.description || "Creative project"}</div>
                  </div>
                  <span className="rounded-full bg-[#25283a] px-2 py-1 text-[10px] text-[#c5c9d8]">{PROJECT_STATUS_LABELS[project.status]}</span>
                  <span className="hidden rounded-[10px] border border-[#363c52] bg-[#222637] px-3 py-2 text-xs font-semibold text-[#e3e6f2] sm:inline">Open</span>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState icon={FolderKanban} title="Your first story starts here" description="Create a film to see your projects here." action={<Button onClick={() => setCreating(true)}>Create a project</Button>} />
          )}
        </>
      )}
    </div>
  );
}

function OverviewCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-[#292d3d] bg-gradient-to-br from-[#171a27] to-[#11131d] p-[19px]">
      <div className="text-[11px] text-[#9ba1b5]">{label.toUpperCase()}</div>
      <div className="my-1 text-[27px] font-bold text-[#f4f5fb] tabular-nums">{value}</div>
      <p className="text-xs text-[#9ba1b5]">{detail}</p>
    </div>
  );
}
