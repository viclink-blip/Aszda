"use client";

import { Clapperboard, Image as ImageIcon, Film, AudioLines } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useCredits } from "@/components/app/credits-context";
import { FilmProgress } from "@/components/director/film-progress";
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
import { formatRelative, providerLabel } from "@/lib/format";
import type { CapabilityRoute, Film as FilmRecord, Job, Scene, SceneGenerationResult } from "@/lib/types";

const IDEA_MAX = 10000;
const DRAFT_KEY = "aszda-director-idea:";

// The unsent idea is kept per project in this browser only; storage can be unavailable.
function readDraft(projectId: string): string {
  try {
    return localStorage.getItem(DRAFT_KEY + projectId) ?? "";
  } catch {
    return "";
  }
}

function writeDraft(projectId: string, text: string) {
  try {
    if (text) localStorage.setItem(DRAFT_KEY + projectId, text);
    else localStorage.removeItem(DRAFT_KEY + projectId);
  } catch {
    // Not saved; the idea still works for this visit.
  }
}

const isPlan = (j: Job) => j.params.task === "director_plan";
const scriptText = (j: Job) => (typeof j.result?.text === "string" ? j.result.text : "");

/** Finished Script Studio answers saved in the project, to start a plan from. */
function ProjectScripts({ scripts, onUse }: { scripts: Job[]; onUse: (job: Job) => void }) {
  if (scripts.length === 0) return null;
  return (
    <div className="rounded-lg border border-line bg-surface-2 p-3">
      <p className="text-sm font-medium text-fg">Scripts in this project</p>
      <ul className="mt-2 flex flex-col gap-2">
        {scripts.slice(0, 5).map((j) => (
          <li key={j.id} className="flex items-center justify-between gap-3 text-sm">
            <span className="min-w-0 truncate text-muted">
              {j.result?.title || scriptText(j).slice(0, 80)}
              <span className="ml-2 text-xs text-subtle">{formatRelative(j.completed_at ?? j.created_at)}</span>
            </span>
            <Button size="sm" variant="outline" onClick={() => onUse(j)}>Use this script</Button>
          </li>
        ))}
      </ul>
    </div>
  );
}

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

function ScenesCard({ projectId, routing, version, onMakeFilm, making, canMakeFilm }: {
  projectId: string; routing: CapabilityRoute[] | undefined; version: number;
  onMakeFilm: () => void; making: boolean; canMakeFilm: boolean;
}) {
  const { data, error, reload } = useApi(() => api.projects.get(projectId), [projectId, version]);
  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  const hasScenes = (data?.scenes.length ?? 0) > 0;
  return (
    <Card>
      <CardHeader title="Scenes"
        description="Create the whole film in one click: ASZDA makes every missing picture, video and voice, then joins all the scenes into one video. Or make each scene yourself."
        action={hasScenes ? (
          <Button size="sm" loading={making} disabled={!canMakeFilm} onClick={onMakeFilm}>
            <Clapperboard className="h-4 w-4" aria-hidden /> Create the whole film
          </Button>
        ) : undefined} />
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
  const params = useSearchParams();
  const [projectId, setProjectId] = useState<string | null>(params.get("project"));
  const [idea, setIdeaState] = useState("");
  const fromJob = params.get("from_job");
  const [loadedFrom, setLoadedFrom] = useState<{ cut: boolean } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const setIdea = (text: string) => {
    setIdeaState(text);
    if (projectId) writeDraft(projectId, text);
  };
  const pickScript = (text: string) => {
    setIdea(text.slice(0, IDEA_MAX));
    setLoadedFrom({ cut: text.length > IDEA_MAX });
  };
  // "Send to AI Film Director" from a Script Studio answer: start from that text.
  useEffect(() => {
    if (!fromJob) return;
    let cancelled = false;
    api.generation.get(fromJob).then(({ job: source }) => {
      const text = scriptText(source);
      if (cancelled || !text) return;
      setIdeaState((current) => current || text.slice(0, IDEA_MAX));
      setLoadedFrom({ cut: text.length > IDEA_MAX });
      if (source.project_id) setProjectId((current) => current ?? source.project_id);
    }).catch((err) => {
      if (!cancelled) setLoadError(errorMessage(err));
    });
    return () => { cancelled = true; };
  }, [fromJob]);
  const [effort, setEffort] = useState<"low" | "medium" | "high">("medium");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  const [version, setVersion] = useState(0);
  const { job, setJob, pollError } = useJobPolling();
  const { data: caps } = useApi(() => api.generation.capabilities(), []);
  // The project's earlier work: its latest plan, and scripts written for it.
  const { data: history } = useApi(
    () => (projectId ? api.generation.list({ project_id: projectId, kind: "text", limit: 50 }) : Promise.resolve(null)),
    [projectId, version],
  );
  const { data: project } = useApi(
    () => (projectId ? api.projects.get(projectId) : Promise.resolve(null)), [projectId, version]);
  const historyFor = history && history.items.every((j) => j.project_id === projectId) ? history.items : null;
  const scripts = (historyFor ?? []).filter((j) => !isPlan(j) && j.status === "completed" && scriptText(j));
  const appliedIds = (project?.project.brief?.director_applied_jobs as string[] | undefined) ?? [];
  const alreadyApplied = applied || (job != null && appliedIds.includes(job.id));
  const [restored, setRestored] = useState(false);
  const [syncedHistory, setSyncedHistory] = useState<typeof history>(undefined);

  // When a project's history arrives: show its latest plan (unless a plan for this project is
  // already on screen) and bring back the unsent idea. Adjusted during render, not in an effect.
  if (projectId && historyFor && history !== syncedHistory) {
    setSyncedHistory(history);
    if (!job || job.project_id !== projectId) {
      setJob(historyFor.find(isPlan) ?? null);
      setRestored(true);
      setApplied(false);
      if (!idea) setIdeaState(readDraft(projectId));
    }
  }
  const routing = caps?.capabilities;
  const planReady = routing?.find((r) => r.kind === "text")?.ready != null;
  const filmReady = planReady && routing?.find((r) => r.kind === "video")?.ready != null;
  const formRef = useRef<HTMLFormElement>(null);
  const [orientation, setOrientation] = useState<"landscape" | "portrait">("landscape");
  const [starting, setStarting] = useState(false);
  const [startedFilm, setStartedFilm] = useState<FilmRecord | null>(null);

  // One click: plan (or use the project's scenes), then every scene's picture, video and voice,
  // joined into one film.
  const makeFilm = async (fromScenes = false) => {
    if (!projectId) return setFormError("Choose a project first.");
    if (!fromScenes && !formRef.current?.reportValidity()) return;
    setStarting(true);
    setFormError(null);
    try {
      const { film } = await api.director.startFilm(projectId,
        fromScenes ? { from_scenes: true, orientation } : { idea, orientation }, newIdempotencyKey());
      setStartedFilm(film);
      toast.success("Your film has started", fromScenes
        ? "ASZDA is making it from your scenes. You can watch the progress below."
        : "ASZDA is planning it now. You can watch the progress below.");
      refresh();
      document.getElementById("film-progress")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      if (fromScenes) toast.error("Could not start the film", errorMessage(err));
      else setFormError(errorMessage(err));
    } finally {
      setStarting(false);
    }
  };

  const plan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId) return setFormError("Choose a project first.");
    setSubmitting(true);
    setFormError(null);
    setApplied(false);
    try {
      const { job: created } = await api.director.plan(projectId, { idea, effort }, newIdempotencyKey());
      setJob(created);
      setRestored(false);
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
      <PageHeader title="AI Film Director" description="Tell your story and click Make my film. ASZDA plans the scenes, makes every picture, video and voice, and joins them into one film." />
      <Notice tone="info" className="mb-6">
        Every step costs credits: the plan, and each scene&apos;s picture, video and voice. After planning, ASZDA
        checks that your balance covers the whole film and waits for you if it does not. Steps that fail are refunded.
      </Notice>
      <ProviderStrip routing={routing} />
      <div className="flex flex-col gap-6">
        <Card id="make-film">
          <CardHeader title="1. Your story" />
          <CardBody>
            <form ref={formRef} onSubmit={plan} className="flex flex-col gap-4">
              <ProjectSelect value={projectId} onChange={setProjectId} required allowCreate help="The plan, scenes and generated files are saved to this project." />
              {loadError && <Notice tone="warning">Your script could not be loaded ({loadError}). Choose it below or paste it.</Notice>}
              {!idea && <ProjectScripts scripts={scripts} onUse={(j) => pickScript(scriptText(j))} />}
              {loadedFrom && (
                <Notice tone="info">
                  Your script was copied into &ldquo;Your idea&rdquo;. You can edit it before creating the plan.
                  {loadedFrom.cut && ` It was longer than ${IDEA_MAX.toLocaleString()} characters, so only the beginning was kept.`}
                </Notice>
              )}
              <Field label="Your idea" required help="Story, audience, tone, length and anything that must appear.">
                {(p) => <Textarea {...p} rows={5} value={idea} minLength={10} maxLength={10000} required onChange={(e) => setIdea(e.target.value)} />}
              </Field>
              <Field label="Shape" help="Use the same shape as where you will share the film.">
                {(p) => (
                  <Select {...p} value={orientation} onChange={(e) => setOrientation(e.target.value as typeof orientation)}>
                    <option value="landscape">Wide 16:9 (YouTube, TV)</option>
                    <option value="portrait">Tall 9:16 (TikTok, Reels, WhatsApp Status)</option>
                  </Select>
                )}
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
              <div className="flex flex-wrap items-center gap-3">
                <Button type="button" size="lg" loading={starting} disabled={!filmReady || submitting} onClick={() => makeFilm()}>
                  <Clapperboard className="h-5 w-5" aria-hidden /> Make my film
                </Button>
                <Button type="submit" variant="outline" loading={submitting} disabled={!planReady || starting}>Only create the plan</Button>
              </div>
              <p className="text-xs text-subtle">
                <b className="font-medium text-muted">Make my film</b> does every step for you and gives you one video.
                A 10-scene film costs about 2,500 credits. <b className="font-medium text-muted">Only create the plan</b> lets
                you review the scenes and make each one yourself.
              </p>
            </form>
          </CardBody>
        </Card>

        {projectId && (
          <div id="film-progress" className="scroll-mt-20">
            <FilmProgress key={projectId} projectId={projectId} startedFilm={startedFilm}
              onChanged={() => setVersion((v) => v + 1)} />
          </div>
        )}

        {job && (
          <Card>
            <CardHeader title="2. Review the plan" action={<StatusBadge status={job.status} />}
              description={restored ? `This project's latest plan, created ${formatRelative(job.created_at)}.` : undefined} />
            <CardBody className="flex flex-col gap-4">
              {pollError && <Notice tone="warning">{pollError}</Notice>}
              {job.status === "completed" ? (
                <>
                  <JobResult job={job} />
                  <div className="flex flex-wrap items-center gap-3">
                    <Button onClick={apply} loading={applying} disabled={alreadyApplied}>{alreadyApplied ? "Added to project" : "Add to project"}</Button>
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

        {projectId && <ScenesCard projectId={projectId} routing={routing} version={version}
          onMakeFilm={() => makeFilm(true)} making={starting} canMakeFilm={filmReady} />}
      </div>
    </>
  );
}
