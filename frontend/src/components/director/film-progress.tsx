"use client";

import { AudioLines, Check, Clapperboard, Download, Film as FilmIcon, Image as ImageIcon, Loader2, Minus, Scissors, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AssetMedia } from "@/components/assets/asset-media";
import { useAssetUrl } from "@/components/assets/use-asset-url";
import { useCredits } from "@/components/app/credits-context";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Notice } from "@/components/ui/notice";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";
import { ACTIVE_FILM_STATUSES, type Film, type FilmStepState } from "@/lib/types";

const POLL_MS = 4000;

const HEADINGS: Record<Film["status"], string> = {
  planning: "Planning your film",
  waiting_for_credits: "Waiting for credits",
  producing: "Making your scenes",
  assembling: "Joining the scenes into one film",
  completed: "Your film is ready",
  failed: "The film could not be finished",
  cancelled: "Film stopped",
};

type StageState = "todo" | "active" | "done" | "skipped";

function StageIcon({ state }: { state: StageState }) {
  if (state === "done") return <Check className="h-4 w-4" aria-hidden />;
  if (state === "active") return <Loader2 className="h-4 w-4 animate-spin" aria-hidden />;
  if (state === "skipped") return <Minus className="h-4 w-4" aria-hidden />;
  return null;
}

function Stage({ icon: Icon, label, detail, state }: {
  icon: typeof ImageIcon; label: string; detail?: string; state: StageState;
}) {
  return (
    <li className={cn("flex items-center gap-3 rounded-lg border px-3 py-2.5",
      state === "active" ? "border-accent bg-accent-soft" : "border-line bg-surface")}>
      <Icon className={cn("h-5 w-5 shrink-0", state === "todo" ? "text-subtle" : "text-accent")} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className={cn("text-sm font-medium", state === "todo" ? "text-muted" : "text-fg")}>{label}</p>
        {detail && <p className="text-xs text-subtle">{detail}</p>}
      </div>
      <span className={cn("grid h-6 w-6 place-items-center rounded-full",
        state === "done" ? "bg-success-soft text-success" : "text-accent")}>
        <StageIcon state={state} />
      </span>
    </li>
  );
}

const STEP_STYLE: Record<FilmStepState, { label: string; className: string }> = {
  waiting: { label: "Waiting", className: "bg-surface-2 text-subtle" },
  running: { label: "Making", className: "bg-accent-soft text-accent" },
  done: { label: "Done", className: "bg-success-soft text-success" },
  failed: { label: "Failed", className: "bg-danger-soft text-danger" },
  skipped: { label: "Not needed", className: "bg-surface-2 text-subtle" },
};

function StepChip({ kind, state, message }: { kind: string; state: FilmStepState; message?: string }) {
  const style = STEP_STYLE[state];
  return (
    <span title={message} className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", style.className)}>
      {kind}: {style.label}
    </span>
  );
}

function stages(film: Film) {
  const planDone = film.scenes.length > 0;
  const kindState = (kind: "image" | "video" | "voice"): StageState => {
    const { done, total } = film.counts[kind];
    if (planDone && total === 0) return "skipped";
    const finished = film.scenes.every((s) => ["done", "failed", "skipped"].includes(s[kind].state));
    if (planDone && finished) return "done";
    if (film.status === "producing" && film.scenes.some((s) => s[kind].state === "running")) return "active";
    return done > 0 ? "active" : "todo";
  };
  const join: StageState = film.status === "completed" ? "done" : film.status === "assembling" ? "active" : "todo";
  return {
    plan: (planDone ? "done" : film.status === "planning" ? "active" : "todo") as StageState,
    image: kindState("image"), video: kindState("video"), voice: kindState("voice"), join,
  };
}

function FilmDownload({ assetId }: { assetId: string }) {
  const { url } = useAssetUrl(assetId);
  if (!url) return null;
  return (
    <a href={url} className="inline-flex h-10 items-center gap-2 rounded-lg bg-brand px-4 text-sm font-medium text-white hover:brightness-110">
      <Download className="h-4 w-4" aria-hidden /> Download film
    </a>
  );
}

/** Progress of the project's automatic film, refreshed until it finishes. */
export function FilmProgress({ projectId, startedFilm, onChanged }: {
  projectId: string;
  /** A film just started from this page, shown at once without waiting for the first load. */
  startedFilm: Film | null;
  /** Called when the film moves to a new stage (for example, so the scene list reloads). */
  onChanged: () => void;
}) {
  const toast = useToast();
  const { refresh } = useCredits();
  const [film, setFilm] = useState<Film | null>(startedFilm);
  const [busy, setBusy] = useState<"continue" | "cancel" | null>(null);
  // Bumped after Continue or Stop, so refreshing starts again (it pauses while a film waits).
  const [pollKey, setPollKey] = useState(0);
  const lastStatus = useRef<string | null>(null);
  const onChangedRef = useRef(onChanged);
  useEffect(() => {
    onChangedRef.current = onChanged;
  });

  // Load and keep refreshing while the film is being made.
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const { film: fresh } = await api.director.currentFilm(projectId);
        if (stopped) return;
        setFilm(fresh);
        const key = fresh ? `${fresh.id}:${fresh.status}:${fresh.scenes.length}` : null;
        if (key !== lastStatus.current) {
          if (lastStatus.current !== null) {
            onChangedRef.current();
            refresh();
          }
          lastStatus.current = key;
        }
        if (fresh && ACTIVE_FILM_STATUSES.includes(fresh.status) && fresh.status !== "waiting_for_credits") {
          timer = setTimeout(load, POLL_MS);
        }
      } catch {
        if (!stopped) timer = setTimeout(load, POLL_MS * 2);
      }
    };
    load();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [projectId, startedFilm, refresh, pollKey]);

  if (!film) return null;
  const s = stages(film);
  const active = ACTIVE_FILM_STATUSES.includes(film.status);
  const total = film.scenes.length;
  const doneSteps = (["image", "video", "voice"] as const).reduce((n, k) => n + film.counts[k].done, 0);
  const allSteps = (["image", "video", "voice"] as const).reduce((n, k) => n + film.counts[k].total, 0);
  const progress = film.status === "completed" ? 100
    : film.status === "planning" ? 5
    : Math.round(10 + 80 * (allSteps ? doneSteps / allSteps : 0) + (film.status === "assembling" ? 5 : 0));

  const act = async (what: "continue" | "cancel") => {
    setBusy(what);
    try {
      const { film: fresh } = what === "continue"
        ? await api.director.continueFilm(projectId, film.id)
        : await api.director.cancelFilm(projectId, film.id);
      setFilm(fresh);
      lastStatus.current = null;
      setPollKey((k) => k + 1);
      if (what === "continue") toast.success("Continuing your film");
      onChangedRef.current();
      refresh();
    } catch (err) {
      toast.error(what === "continue" ? "Could not continue" : "Could not stop the film", errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className={cn(film.status === "completed" && "border-accent")}>
      <CardHeader
        title={HEADINGS[film.status]}
        description={film.status === "completed"
          ? `${total} scenes · ${formatNumber(film.credits_charged)} credits used`
          : active && film.status !== "waiting_for_credits"
            ? "You can leave this page. Your film keeps being made, and it is saved in this project." : undefined}
        action={active && film.status !== "assembling" ? (
          <Button size="sm" variant="ghost" loading={busy === "cancel"} onClick={() => act("cancel")}>
            <X className="h-4 w-4" aria-hidden /> Stop
          </Button>
        ) : undefined}
      />
      <CardBody className="flex flex-col gap-5">
        {film.status === "completed" && film.film_asset && (
          <div className="flex flex-col gap-3">
            <AssetMedia asset={film.film_asset} />
            <div className="flex flex-wrap items-center gap-3">
              <FilmDownload assetId={film.film_asset.id} />
              <ButtonLink href={`/app/projects/${projectId}?tab=assets`} variant="outline">Open project files</ButtonLink>
            </div>
          </div>
        )}

        {film.status === "waiting_for_credits" && (
          <Notice tone="warning" title="Your film is paused" action={
            <div className="flex flex-wrap gap-2">
              <Button size="sm" loading={busy === "continue"} onClick={() => act("continue")}>Continue</Button>
              <ButtonLink size="sm" variant="outline" href="/app/billing">Add credits</ButtonLink>
            </div>
          }>
            {film.error?.message ?? "Add credits, then click Continue."}
          </Notice>
        )}
        {film.status === "failed" && (
          <Notice tone="danger" title="Something went wrong">
            {film.error?.message ?? "Please try again."} Credits for steps that failed were returned.
          </Notice>
        )}
        {film.status === "cancelled" && (
          <Notice tone="info">No new steps were started after you stopped. Finished scenes are kept in the project.</Notice>
        )}

        {active && <Progress value={progress} label="Film progress" />}

        <ol className="grid gap-2 sm:grid-cols-5">
          <Stage icon={Clapperboard} label="Plan" detail={total ? `${total} scenes` : undefined} state={s.plan} />
          <Stage icon={ImageIcon} label="Pictures" detail={total ? `${film.counts.image.done} of ${film.counts.image.total}` : undefined} state={s.image} />
          <Stage icon={FilmIcon} label="Videos" detail={total ? `${film.counts.video.done} of ${film.counts.video.total}` : undefined} state={s.video} />
          <Stage icon={AudioLines} label="Voices" detail={total ? `${film.counts.voice.done} of ${film.counts.voice.total}` : undefined} state={s.voice} />
          <Stage icon={Scissors} label="Join" detail={film.status === "completed" ? "One video" : undefined} state={s.join} />
        </ol>

        {film.estimated_credits != null && active && (
          <p className="text-xs text-subtle">
            Estimated cost: about {formatNumber(film.estimated_credits)} credits. Used so far: {formatNumber(film.credits_charged)}.
            Steps that fail are refunded.
          </p>
        )}

        {total > 0 && (
          <details className="rounded-lg border border-line">
            <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-fg">Scene by scene</summary>
            <ul className="divide-y divide-line">
              {film.scenes.map((scene, i) => (
                <li key={scene.scene_id} className="flex flex-col gap-1.5 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
                  <span className="text-sm text-fg">
                    <span className="mr-2 font-mono text-xs text-subtle tabular-nums">{String(i + 1).padStart(2, "0")}</span>
                    {scene.title}
                  </span>
                  <span className="flex flex-wrap gap-1.5">
                    <StepChip kind="Picture" state={scene.image.state} message={scene.image.message} />
                    <StepChip kind="Video" state={scene.video.state} message={scene.video.message} />
                    <StepChip kind="Voice" state={scene.voice.state} message={scene.voice.message} />
                  </span>
                </li>
              ))}
            </ul>
          </details>
        )}
        {(film.status === "failed" || film.status === "cancelled") && (
          <p className="text-sm text-muted">
            You can make the remaining scenes yourself below, or <Link className="text-accent underline" href="#make-film">start a new film</Link>.
          </p>
        )}
      </CardBody>
    </Card>
  );
}
