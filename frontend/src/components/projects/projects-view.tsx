"use client";

import { FolderKanban, Plus, Search } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useDebounced } from "@/hooks/use-debounced";
import { api } from "@/lib/api";
import { PROJECT_STATUS_LABELS } from "@/lib/format";
import type { ProjectStatus } from "@/lib/types";
import { CreateProjectDialog } from "./create-project-dialog";
import { ProjectCard } from "./project-card";

const PAGE_SIZE = 24;

export function ProjectsView() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ProjectStatus | "">("");
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);
  const search = useDebounced(query.trim());

  const { data, error, loading, reload } = useApi(
    () => api.projects.list({ q: search, status, limit: PAGE_SIZE, offset }),
    [search, status, offset],
  );

  const filtered = Boolean(search || status);

  return (
    <>
      <PageHeader
        title="Projects"
        description="Each project holds one story's characters, storyboard, assets and generations."
        actions={<Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" aria-hidden /> New project</Button>}
      />
      <CreateProjectDialog open={creating} onOpenChange={setCreating} />

      <div className="mb-6 flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-subtle" aria-hidden />
          <Input
            type="search"
            aria-label="Search projects by title"
            placeholder="Search projects"
            className="pl-9"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOffset(0);
            }}
          />
        </div>
        <div className="sm:w-48">
          <Select aria-label="Filter by status" value={status} onChange={(e) => { setStatus(e.target.value as ProjectStatus | ""); setOffset(0); }}>
            <option value="">All statuses</option>
            {Object.entries(PROJECT_STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </Select>
        </div>
      </div>

      {error && !data ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" role="status" aria-label="Loading projects">
          {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-40" />)}
        </div>
      ) : data.items.length === 0 ? (
        filtered ? (
          <EmptyState icon={Search} title="No matching projects" description="Try a different search or status filter." />
        ) : (
          <EmptyState
            icon={FolderKanban}
            title="Start your first project"
            description="Give it a title — you can add characters, scenes and generations afterwards."
            action={<Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" aria-hidden /> New project</Button>}
          />
        )
      ) : (
        <>
          <p className="mb-3 text-sm text-subtle" aria-live="polite">
            {data.total} project{data.total === 1 ? "" : "s"}{loading ? " · updating…" : ""}
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.items.map((project) => <ProjectCard key={project.id} project={project} />)}
          </div>
          <Pagination offset={offset} limit={PAGE_SIZE} total={data.total} onChange={setOffset} />
        </>
      )}
    </>
  );
}
