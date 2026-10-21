"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { ErrorState } from "@/components/ui/error-state";
import { useModels } from "@/hooks/use-providers";
import type { GenerationKind, Job } from "@/lib/types";
import { GenerationForm } from "./generation-form";
import { OutputPanel } from "./output-panel";
import { ProjectSelect } from "./project-select";
import { RecentJobs } from "./recent-jobs";

/**
 * Layout shared by the Script, Video and Voice studios:
 * project + model + settings on the left, live output on the right.
 */
export function StudioView({ kind, title, description, notes, submitLabel, emptyText }: {
  kind: GenerationKind;
  title: string;
  description: string;
  /** Honest notes shown above the form (what this studio does and does not do). */
  notes?: React.ReactNode;
  submitLabel: string;
  emptyText: string;
}) {
  const initialProject = useSearchParams().get("project");
  const [projectId, setProjectId] = useState<string | null>(initialProject);
  const [job, setJob] = useState<Job | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const { options, loading, error, reload } = useModels(kind);

  const started = (created: Job) => {
    setJob(created);
    setRefreshKey((k) => k + 1);
  };

  return (
    <>
      <PageHeader eyebrow="Studio" title={title} description={description} />
      {notes && <div className="mb-6 flex flex-col gap-3">{notes}</div>}
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <div className="flex flex-col gap-6">
          <ProjectSelect value={projectId} onChange={setProjectId} />
          {error && !loading ? (
            <ErrorState error={error} onRetry={reload} title="Could not load the models" />
          ) : (
            <GenerationForm
              kind={kind}
              options={options}
              loadingModels={loading}
              projectId={projectId}
              submitLabel={submitLabel}
              onCreated={started}
            />
          )}
        </div>
        <div className="lg:sticky lg:top-24 lg:self-start">
          <OutputPanel job={job} onRetried={started} emptyText={emptyText} />
          <RecentJobs kind={kind} refreshKey={refreshKey} excludeId={job?.id} />
        </div>
      </div>
    </>
  );
}
