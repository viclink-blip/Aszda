"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { StatusBadge } from "@/components/ui/badge";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApi } from "@/hooks/use-api";
import { api, ApiError } from "@/lib/api";
import type { ProjectDetail } from "@/lib/types";
import { AssetsTab } from "./assets-tab";
import { CharactersTab } from "./characters-tab";
import { GenerationsTab } from "./generations-tab";
import { OverviewTab } from "./overview-tab";
import { StoryboardTab } from "./storyboard-tab";

const TABS = ["overview", "characters", "storyboard", "assets", "generations"] as const;
type Tab = (typeof TABS)[number];

/** Shared by the tabs: the loaded project and a way to update it locally. */
export interface ProjectTabProps {
  detail: ProjectDetail;
  update: (change: (detail: ProjectDetail) => ProjectDetail) => void;
  reload: () => Promise<void>;
}

export function ProjectWorkspace() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const requested = searchParams.get("tab") as Tab | null;
  const tab: Tab = requested && TABS.includes(requested) ? requested : "overview";

  const { data, error, reload, setData } = useApi(() => api.projects.get(id), [id]);

  // Keep the tab in the URL so it survives reloads and can be linked to.
  const changeTab = (value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value === "overview") params.delete("tab");
    else params.set("tab", value);
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  if (error && !data) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <>
        <BackLink />
        <ErrorState
          error={error}
          title={notFound ? "Project not found" : "Could not load this project"}
          onRetry={notFound ? undefined : reload}
        />
      </>
    );
  }

  if (!data) {
    return (
      <div role="status" aria-label="Loading project">
        <BackLink />
        <Skeleton className="h-9 w-2/3 max-w-sm" />
        <Skeleton className="mt-6 h-10 w-full" />
        <Skeleton className="mt-6 h-64 w-full" />
      </div>
    );
  }

  const tabProps: ProjectTabProps = {
    detail: data,
    update: (change) => setData((d) => (d ? change(d) : d)),
    reload,
  };

  return (
    <>
      <BackLink />
      <header className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="min-w-0 font-display text-2xl font-semibold tracking-tight break-words text-fg sm:text-3xl">{data.project.title}</h1>
        <StatusBadge status={data.project.status} />
      </header>
      <Tabs value={tab} onValueChange={changeTab}>
        <TabsList aria-label="Project sections">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="characters">Characters <Count n={data.characters.length} /></TabsTrigger>
          <TabsTrigger value="storyboard">Storyboard <Count n={data.scenes.length} /></TabsTrigger>
          <TabsTrigger value="assets">Assets</TabsTrigger>
          <TabsTrigger value="generations">Generations</TabsTrigger>
        </TabsList>
        <div className="pt-6">
          <TabsContent value="overview"><OverviewTab {...tabProps} /></TabsContent>
          <TabsContent value="characters"><CharactersTab {...tabProps} /></TabsContent>
          <TabsContent value="storyboard"><StoryboardTab {...tabProps} /></TabsContent>
          <TabsContent value="assets"><AssetsTab {...tabProps} /></TabsContent>
          <TabsContent value="generations"><GenerationsTab {...tabProps} /></TabsContent>
        </div>
      </Tabs>
    </>
  );
}

function Count({ n }: { n: number }) {
  return <span className="rounded-full bg-surface-2 px-1.5 text-xs text-subtle tabular-nums">{n}</span>;
}

function BackLink() {
  return (
    <Link href="/app/projects" className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg">
      <ArrowLeft className="h-4 w-4" aria-hidden /> Projects
    </Link>
  );
}
