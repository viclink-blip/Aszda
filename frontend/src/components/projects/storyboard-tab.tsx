"use client";

import { ArrowDown, ArrowUp, Clock, LayoutList, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import type { Scene } from "@/lib/types";
import type { ProjectTabProps } from "./project-workspace";
import { SceneFormDialog } from "./scene-form-dialog";

export function StoryboardTab({ detail, update }: ProjectTabProps) {
  const projectId = detail.project.id;
  const toast = useToast();
  const [editing, setEditing] = useState<Scene | null | undefined>(undefined);
  const [deleting, setDeleting] = useState<Scene | null>(null);
  const [moving, setMoving] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");

  const scenes = [...detail.scenes].sort((a, b) => a.position - b.position);
  const characterName = new Map(detail.characters.map((c) => [c.id, c.name]));
  const totalSeconds = scenes.reduce((sum, s) => sum + (s.duration_seconds ?? 0), 0);

  const saved = (scene: Scene) => {
    const isNew = !detail.scenes.some((s) => s.id === scene.id);
    update((d) => ({
      ...d,
      scenes: isNew ? [...d.scenes, scene] : d.scenes.map((s) => (s.id === scene.id ? scene : s)),
    }));
    toast.success(isNew ? "Scene added" : "Scene saved", scene.title);
  };

  /** Swap a scene with its neighbour and save the new order. */
  const move = async (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= scenes.length) return;
    const order = scenes.map((s) => s.id);
    [order[index], order[target]] = [order[target], order[index]];
    setMoving(scenes[index].id);
    try {
      const { scenes: reordered } = await api.scenes.reorder(projectId, order);
      update((d) => ({ ...d, scenes: reordered }));
      setAnnouncement(`${scenes[index].title} moved to position ${target + 1} of ${scenes.length}.`);
    } catch (error) {
      toast.error("Could not reorder scenes", errorMessage(error));
    } finally {
      setMoving(null);
    }
  };

  const remove = async () => {
    if (!deleting) return;
    try {
      await api.scenes.remove(projectId, deleting.id);
    } catch (error) {
      throw new Error(errorMessage(error));
    }
    const id = deleting.id;
    // Positions of the remaining scenes change; reload them from the server.
    try {
      const fresh = await api.projects.get(projectId);
      update((d) => ({ ...d, scenes: fresh.scenes }));
    } catch {
      update((d) => ({ ...d, scenes: d.scenes.filter((s) => s.id !== id) }));
    }
    toast.success("Scene deleted");
  };

  return (
    <section aria-labelledby="storyboard-heading">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="storyboard-heading" className="font-display text-lg font-semibold text-fg">Storyboard</h2>
          <p className="text-sm text-muted">
            {scenes.length} scene{scenes.length === 1 ? "" : "s"}
            {totalSeconds > 0 && <> · about {formatDuration(totalSeconds)} in total</>}
          </p>
        </div>
        <Button onClick={() => setEditing(null)}><Plus className="h-4 w-4" aria-hidden /> Add scene</Button>
      </div>
      <p className="sr-only" aria-live="polite">{announcement}</p>

      {scenes.length === 0 ? (
        <EmptyState
          icon={LayoutList}
          title="No scenes yet"
          description="Break your story into scenes. Add shot notes, dialogue, length and which characters appear."
          action={<Button onClick={() => setEditing(null)}><Plus className="h-4 w-4" aria-hidden /> Add the first scene</Button>}
        />
      ) : (
        <ol className="flex flex-col gap-3">
          {scenes.map((scene, index) => (
            <li key={scene.id} className="flex gap-3 rounded-xl border border-line bg-surface p-4 sm:gap-4">
              <div className="flex flex-col items-center gap-1">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-2 font-mono text-sm text-fg tabular-nums">
                  {index + 1}
                </span>
                <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => move(index, -1)} disabled={index === 0 || moving !== null} aria-label={`Move ${scene.title} up`}>
                  <ArrowUp className="h-4 w-4" aria-hidden />
                </Button>
                <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => move(index, 1)} disabled={index === scenes.length - 1 || moving !== null} aria-label={`Move ${scene.title} down`}>
                  <ArrowDown className="h-4 w-4" aria-hidden />
                </Button>
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <h3 className="font-display font-semibold break-words text-fg">{scene.title}</h3>
                  {scene.duration_seconds && (
                    <span className="inline-flex items-center gap-1 text-xs text-subtle">
                      <Clock className="h-3.5 w-3.5" aria-hidden /> {formatDuration(scene.duration_seconds)}
                    </span>
                  )}
                </div>
                {scene.description && <p className="mt-1 text-sm whitespace-pre-line text-muted">{scene.description}</p>}
                {scene.shot_notes && (
                  <p className="mt-2 text-sm text-muted"><span className="font-medium text-fg">Shot: </span>{scene.shot_notes}</p>
                )}
                {scene.dialogue && (
                  <p className="mt-2 border-l-2 border-line-strong pl-3 text-sm whitespace-pre-line text-muted italic">{scene.dialogue}</p>
                )}
                {scene.character_ids.length > 0 && (
                  <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Characters in this scene">
                    {scene.character_ids.map((id) => (
                      <li key={id} className="rounded-full bg-surface-2 px-2.5 py-0.5 text-xs text-muted">{characterName.get(id) ?? "Unknown"}</li>
                    ))}
                  </ul>
                )}
                <div className="mt-3 flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => setEditing(scene)}>
                    <Pencil className="h-3.5 w-3.5" aria-hidden /> Edit
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setDeleting(scene)} aria-label={`Delete ${scene.title}`}>
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}

      {editing !== undefined && (
        <SceneFormDialog
          key={editing?.id ?? "new"}
          projectId={projectId}
          scene={editing}
          characters={detail.characters}
          open
          onOpenChange={(open) => !open && setEditing(undefined)}
          onSaved={saved}
        />
      )}
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete scene?"
        description={<>Delete <strong className="text-fg">{deleting?.title}</strong> from the storyboard? This cannot be undone.</>}
        confirmLabel="Delete"
        destructive
        onConfirm={remove}
      />
    </section>
  );
}
