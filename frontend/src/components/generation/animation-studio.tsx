"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { AssetMedia } from "@/components/assets/asset-media";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/input";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useModels } from "@/hooks/use-providers";
import { api } from "@/lib/api";
import type { Job, ProjectDetail, Scene } from "@/lib/types";
import { GenerationForm } from "./generation-form";
import { OutputPanel } from "./output-panel";
import { ProjectSelect } from "./project-select";
import { RecentJobs } from "./recent-jobs";

/** The scene's text, used as a starting prompt (Runway accepts up to 1000 characters). */
function scenePrompt(scene: Scene | undefined): string {
  if (!scene) return "";
  return [scene.description, scene.shot_notes].filter(Boolean).join(" ").slice(0, 1000);
}

export function AnimationStudio() {
  const params = useSearchParams();
  const [projectId, setProjectId] = useState<string | null>(params.get("project"));
  const [characterId, setCharacterId] = useState<string | null>(params.get("character"));
  const [sceneId, setSceneId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const models = useModels("video");
  const project = useApi<ProjectDetail | null>(
    () => (projectId ? api.projects.get(projectId) : Promise.resolve(null)),
    [projectId],
  );

  const detail = project.data ?? null;
  const characters = detail?.characters ?? [];
  const character = characters.find((c) => c.id === characterId && c.reference_asset_id);
  const scenes = [...(detail?.scenes ?? [])].sort((a, b) => a.position - b.position);
  const scene = scenes.find((s) => s.id === sceneId);

  const changeProject = (id: string | null) => {
    setProjectId(id);
    setCharacterId(null);
    setSceneId(null);
  };

  const started = (created: Job) => {
    setJob(created);
    setRefreshKey((k) => k + 1);
  };

  const blocked = !projectId
    ? "Choose a project first."
    : !character
      ? "Choose a character with a reference image."
      : null;

  return (
    <>
      <PageHeader
        eyebrow="Studio"
        title="Animation Studio"
        description="Animate a character from your project: their still reference image becomes the first frame of a short video clip."
      />
      <Notice tone="info" className="mb-6" title="How this works today">
        ASZDA sends the character&apos;s reference image and your scene description to an image-to-video model (Runway).
        It animates that still image into one short clip; it does not build a 3D or rigged character. Characters and
        storyboards are structured planning data you manage in your project.
      </Notice>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <div className="flex flex-col gap-6">
          <ProjectSelect value={projectId} onChange={changeProject} required help="Animation uses a character from one of your projects." />

          {projectId && project.loading && !detail ? (
            <Skeleton className="h-24" />
          ) : detail ? (
            <>
              {characters.length === 0 ? (
                <Notice tone="warning" title="This project has no characters yet">
                  <Link href={`/app/projects/${projectId}?tab=characters`} className="underline">Add a character</Link> with a reference image first.
                </Notice>
              ) : (
                <Field label="Character" required help="Only characters with a reference image can be animated.">
                  {(p) => (
                    <Select {...p} value={characterId ?? ""} onChange={(e) => setCharacterId(e.target.value || null)}>
                      <option value="" disabled>Choose a character…</option>
                      {characters.map((c) => (
                        <option key={c.id} value={c.id} disabled={!c.reference_asset_id}>
                          {c.name}{c.reference_asset_id ? "" : " (needs a reference image)"}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              )}
              {character && character.reference_asset_id && (
                <div className="grid gap-4 rounded-xl border border-line bg-surface p-4 sm:grid-cols-[10rem_1fr]">
                  <AssetMedia asset={{ id: character.reference_asset_id, kind: "image", display_name: `${character.name} reference` }} compact />
                  <div className="min-w-0">
                    <p className="font-medium text-fg">{character.name}</p>
                    <p className="mt-1 line-clamp-4 text-sm text-muted">{character.description || "No description."}</p>
                  </div>
                </div>
              )}
              <Field label="Scene (optional)" help="Link the clip to a storyboard scene and start from its description.">
                {(p) => (
                  <Select {...p} value={sceneId ?? ""} onChange={(e) => setSceneId(e.target.value || null)}>
                    <option value="">No scene</option>
                    {scenes.map((s, i) => <option key={s.id} value={s.id}>{i + 1}. {s.title}</option>)}
                  </Select>
                )}
              </Field>
            </>
          ) : null}

          <GenerationForm
            // Remount when the character or scene changes so the prompt starts from the scene again.
            key={`${characterId}-${sceneId}`}
            kind="video"
            options={models.options}
            loadingModels={models.loading}
            projectId={projectId}
            sceneId={sceneId}
            fixedValues={{ mode: "image_to_video", reference_asset_id: character?.reference_asset_id ?? null }}
            initialOverrides={scene ? { prompt_text: scenePrompt(scene) } : {}}
            blockedReason={blocked}
            submitLabel="Animate character"
            onCreated={started}
          />
        </div>
        <div className="lg:sticky lg:top-24 lg:self-start">
          <OutputPanel job={job} onRetried={started} emptyText="Your animated clip will play here when it is ready." />
          <RecentJobs kind="video" refreshKey={refreshKey} excludeId={job?.id} />
        </div>
      </div>
    </>
  );
}
