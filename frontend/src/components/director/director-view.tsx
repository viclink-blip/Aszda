"use client";

import { Clapperboard, Image as ImageIcon, Film, AudioLines } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useCredits } from "@/components/app/credits-context";
import { JobResult } from "@/components/generation/job-result";
import { ProjectSelect } from "@/components/generation/project-select";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Field, FormError } from "@/components/ui/field";
import { Select, Textarea } from "@/components/ui/input";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { LoadingRows } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useJobPolling } from "@/hooks/use-job-polling";
import { api, errorMessage, newIdempotencyKey } from "@/lib/api";
import { providerLabel } from "@/lib/format";
import type { CapabilityRoute, Scene, SceneGenerationResult } from "@/lib/types";

type SceneKind = "image" | "video" | "voice";
const KIND_INFO: Record<SceneKind, { label: string; icon: typeof ImageIcon; route: CapabilityRoute["kind"] }> = {
  image: { label: "Image", icon: ImageIcon, route: "image" },
  video: { label: "Video", icon: Film, route: "video" },
  voice: { label: "Voice", icon: AudioLines, route: "speech" },
};

/** Which provider each step will use, so nobody is surprised by where a job goes. */
function ProviderStrip({ routing }: { routing: CapabilityRoute[] | undefined }) {
  if (!routing) return null;
  const labels: Record<string, string> = { text: "Planning", image: "Images", video: "Video", speech: "Voice" };
  return (
    <ul className="mb-6 grid gap-2 sm:grid-cols-4">
      {routing.map((r) => (
        <li key={r.kind} className="rounded-lg border border-line bg-surface px-3 py-2 text-sm">
          <p className="text-xs text-subtle">{labels[r.kind]}</p>
          {r.ready ? (
            <p className="text-fg">{providerLabel(r.ready.provider)} <span className="font-mono text-xs text-subtle">{r.ready.model}</span></p>
          ) : (
            <p className="text-warning">Not set up yet</p>
          )}
        </li>
      ))}
    </ul>
  );
}

function SceneRow({ projectId, scene, routing }: { projectId: string; scene: Scene; routing: CapabilityRoute[] | undefined }) {
  const toast = useToast();
  const { refresh } = useCredits();
  const [busy, setBusy] = useState<SceneKind | "all" | null>(null);
  const [results, setResults] = useState<SceneGenerationResult[]>([]);
  const ready = (kind: SceneKind) => routing?.find((r) => r.kind === KIND_INFO[kind].route)?.ready != null;

  const generate = async (kinds: SceneKind[], label: SceneKind | "all") => {
    setBusy(label);
    try {
      const { results: started } = await api.director.generateScene(projectId, scene.id, { kinds }, newIdempotencyKey());
      setResults((prev) => [...started, ...prev]);
      const failed = started.filter((r) => r.error);
      if (failed.length) toast.error("Some generations could not start", failed.map((r) => r.error?.message).join(" "));
      else toast.success("Generation started", "Credits are reserved now; unused credits come back when each job finishes.");
      refresh();
    } catch (err) {
      toast.error("Could not start the generation", errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const prompts = scene.ai_prompts ?? {};
  return (
    <li className="flex flex-col gap-3 px-5 py-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-medium text-fg">
            <span className="mr-2 font-mono text-xs text-subtle tabular-nums">{String(scene.position + 1).padStart(2, "0")}</span>
            {scene.title}
            {scene.duration_seconds && <span className="ml-2 text-xs text-subtle">{scene.duration_seconds} s</span>}
          </p>
          <p className="mt-1 text-sm text-muted">{scene.description}</p>
          {prompts.narration && <p className="mt-1 text-xs text-subtle">Narration: {prompts.narration}</p>}
          {scene.preview_asset_id && <Badge tone="success" className="mt-2">Has a key frame (video will start from it)</Badge>}
        </div>
        <div className="flex flex-wrap gap-2 sm:justify-end">
          {(Object.keys(KIND_INFO) as SceneKind[]).map((kind) => {
            const { label, icon: Icon } = KIND_INFO[kind];
            return (
              <Button key={kind} size="sm" variant="secondary" loading={busy === kind} disabled={busy !== null || !ready(kind)}
                onClick={() => generate([kind], kind)} title={ready(kind) ? undefined : "No provider is set up for this yet"}>
                <Icon className="size-4" aria-hidden /> {label}
              </Button>
            );
          })}
        </div>
      </div>
      {results.length > 0 && (
        <ul className="flex flex-col gap-1 text-xs">
          {results.map((r, i) => (
            <li key={`${r.kind}-${r.job_id ?? i}`} className="text-muted">
              {KIND_INFO[r.kind].label}:{" "}
              {r.job_id ? (
                <Link className="text-fg hover:text-accent" href={`/app/generations?kind=${r.kind === "voice" ? "speech" : r.kind}`}>
                  {r.created ? "started" : "already started"} with {providerLabel(r.provider ?? "")} {r.model}
                </Link>
              ) : r.skipped ? r.skipped : <span className="text-danger">{r.error?.message}</span>}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function ScenesCard({ projectId, routing, version }: { projectId: string; routing: CapabilityRoute[] | undefined; version: number }) {
  const { data, error, reload } = useApi(() => api.projects.get(projectId), [projectId, version]);
  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  return (
    <Card>
      <CardHeader title="Scenes" description="Generate each scene's key frame image, video and voice. Every generation is a normal job that reserves credits first." />
      {!data ? <div className="p-5"><LoadingRows rows={3} /></div> : data.scenes.length === 0 ? (
        <EmptyState className="m-5" icon={Clapperboard} title="No scenes yet" description="Create a plan above and add it to the project." />
      ) : (
        <ul className="divide-y divide-line">
          {data.scenes.map((scene) => <SceneRow key={scene.id} projectId={projectId} scene={scene} routing={routing} />)}
        </ul>
      )}
    </Card>
  );
}

export function DirectorView() {
  const toast = useToast();
  const { refresh } = useCredits();
  const [projectId, setProjectId] = useState<string | null>(useSearchParams().get("project"));
  const [idea, setIdea] = useState("");
  const [effort, setEffort] = useState<"low" | "medium" | "high">("medium");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  const [version, setVersion] = useState(0);
  const { job, setJob, pollError } = useJobPolling();
  const { data: caps } = useApi(() => api.generation.capabilities(), []);
  const routing = caps?.capabilities;
  const planReady = routing?.find((r) => r.kind === "text")?.ready != null;

  const plan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId) return setFormError("Choose a project first.");
    setSubmitting(true);
    setFormError(null);
    setApplied(false);
    try {
      const { job: created } = await api.director.plan(projectId, { idea, effort }, newIdempotencyKey());
      setJob(created);
      refresh();
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const apply = async () => {
    if (!projectId || !job) return;
    setApplying(true);
    try {
      const { scenes } = await api.director.apply(projectId, job.id);
      toast.success("Plan added to the project", `${scenes.length} scenes and their characters were added.`);
      setApplied(true);
      setVersion((v) => v + 1);
    } catch (err) {
      toast.error("Could not add the plan", errorMessage(err));
    } finally {
      setApplying(false);
    }
  };

  return (
    <>
      <PageHeader title="AI Film Director" description="Describe a film. Claude plans the characters and scenes; you review the plan, add it to a project, then generate each scene." />
      <Notice tone="info" className="mb-6">
        Each step is a normal generation that costs credits: the plan (text), and each scene&apos;s image, video and
        voice. Credits are reserved before a job starts and unused credits are returned. Joining the clips into one
        exported film is not available yet — download each scene&apos;s files from the project.
      </Notice>
      <ProviderStrip routing={routing} />
      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader title="1. Plan the film" />
          <CardBody>
            <form onSubmit={plan} className="flex flex-col gap-4">
              <ProjectSelect value={projectId} onChange={setProjectId} required help="The plan, scenes and generated files are saved to this project." />
              <Field label="Your idea" required help="Story, audience, tone, length and anything that must appear.">
                {(p) => <Textarea {...p} rows={5} value={idea} minLength={10} maxLength={10000} required onChange={(e) => setIdea(e.target.value)} />}
              </Field>
              <Field label="Planning effort">
                {(p) => (
                  <Select {...p} value={effort} onChange={(e) => setEffort(e.target.value as typeof effort)}>
                    <option value="low">Low (faster)</option>
                    <option value="medium">Medium</option>
                    <option value="high">High (more thorough)</option>
                  </Select>
                )}
              </Field>
              <FormError message={formError} />
              {!planReady && routing && <Notice tone="warning">No text provider is set up yet, so plans cannot be created.</Notice>}
              <div><Button type="submit" loading={submitting} disabled={!planReady}>Create plan</Button></div>
            </form>
          </CardBody>
        </Card>

        {job && (
          <Card>
            <CardHeader title="2. Review the plan" action={<StatusBadge status={job.status} />} />
            <CardBody className="flex flex-col gap-4">
              {pollError && <Notice tone="warning">{pollError}</Notice>}
              {job.status === "completed" ? (
                <>
                  <JobResult job={job} />
                  <div className="flex flex-wrap items-center gap-3">
                    <Button onClick={apply} loading={applying} disabled={applied}>{applied ? "Added to project" : "Add to project"}</Button>
                    <span className="text-xs text-subtle">Adds the characters and scenes; your existing scenes are kept.</span>
                  </div>
                </>
              ) : job.status === "failed" || job.status === "cancelled" ? (
                <Notice tone="danger" title="The plan could not be created">{job.error?.message ?? "Please try again."} Unused credits were returned.</Notice>
              ) : (
                <p className="text-sm text-muted">Claude is planning your film. This can take a minute or two.</p>
              )}
            </CardBody>
          </Card>
        )}

        {projectId && <ScenesCard projectId={projectId} routing={routing} version={version} />}
      </div>
    </>
  );
}
