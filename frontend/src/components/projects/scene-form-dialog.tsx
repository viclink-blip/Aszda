"use client";

import { useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, FormError } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { focusFirstError, splitErrors } from "@/lib/forms";
import type { Character, Scene } from "@/lib/types";

/** Add or edit a storyboard scene. `scene` = null means "add at the end". */
export function SceneFormDialog({ projectId, scene, characters, open, onOpenChange, onSaved }: {
  projectId: string;
  scene: Scene | null;
  characters: Character[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (scene: Scene) => void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const castId = useId();
  const [form, setForm] = useState({
    title: scene?.title ?? "",
    description: scene?.description ?? "",
    shot_notes: scene?.shot_notes ?? "",
    dialogue: scene?.dialogue ?? "",
    duration: scene?.duration_seconds ? String(scene.duration_seconds) : "",
  });
  const [cast, setCast] = useState<string[]>(scene?.character_ids ?? []);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const toggleCast = (id: string) =>
    setCast((list) => (list.includes(id) ? list.filter((c) => c !== id) : [...list, id]));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};
    if (!form.title.trim()) nextErrors.title = "Give the scene a title.";
    const duration = form.duration.trim() === "" ? null : Number(form.duration);
    if (duration !== null && (!Number.isInteger(duration) || duration < 1 || duration > 3600)) {
      nextErrors.duration_seconds = "Use a whole number of seconds between 1 and 3600.";
    }
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      focusFirstError(formRef.current);
      return;
    }
    setBusy(true);
    setErrors({});
    setFormError(null);
    const body = {
      title: form.title.trim(),
      description: form.description,
      shot_notes: form.shot_notes,
      dialogue: form.dialogue,
      duration_seconds: duration,
      character_ids: cast,
    };
    try {
      const { scene: saved } = scene
        ? await api.scenes.update(projectId, scene.id, body)
        : await api.scenes.create(projectId, body);
      onSaved(saved);
      onOpenChange(false);
    } catch (error) {
      const split = splitErrors(error, ["title", "description", "shot_notes", "dialogue", "duration_seconds", "character_ids"]);
      setErrors(split.fieldErrors);
      setFormError(split.formError);
      focusFirstError(formRef.current);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={scene ? "Edit scene" : "Add scene"} size="lg">
      <form ref={formRef} onSubmit={submit} noValidate className="flex flex-col gap-4">
        <FormError message={formError} />
        <div className="grid gap-4 sm:grid-cols-[1fr_9rem]">
          <Field label="Scene title" required error={errors.title}>
            {(p) => <Input {...p} maxLength={120} value={form.title} onChange={set("title")} placeholder="e.g. Storm at the lighthouse" autoFocus />}
          </Field>
          <Field label="Length (seconds)" error={errors.duration_seconds}>
            {(p) => <Input {...p} type="number" inputMode="numeric" min={1} max={3600} value={form.duration} onChange={set("duration")} />}
          </Field>
        </div>
        <Field label="What happens" error={errors.description}>
          {(p) => <Textarea {...p} rows={3} maxLength={10000} value={form.description} onChange={set("description")} />}
        </Field>
        <Field label="Shot notes" error={errors.shot_notes} help="Framing, camera movement, lighting, mood.">
          {(p) => <Textarea {...p} rows={2} maxLength={5000} value={form.shot_notes} onChange={set("shot_notes")} />}
        </Field>
        <Field label="Dialogue" error={errors.dialogue}>
          {(p) => <Textarea {...p} rows={3} maxLength={10000} value={form.dialogue} onChange={set("dialogue")} />}
        </Field>
        <fieldset aria-describedby={errors.character_ids ? `${castId}-err` : undefined}>
          <legend className="text-sm font-medium text-fg">Characters in this scene</legend>
          {characters.length === 0 ? (
            <p className="mt-1.5 text-sm text-subtle">No characters yet. Add them in the Characters tab.</p>
          ) : (
            <div className="mt-2 flex flex-wrap gap-2">
              {characters.map((c) => {
                const checked = cast.includes(c.id);
                return (
                  <label
                    key={c.id}
                    className={`flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-sm ${checked ? "border-accent bg-accent-soft text-fg" : "border-line text-muted"}`}
                  >
                    <input type="checkbox" className="h-3.5 w-3.5 accent-[var(--accent)]" checked={checked} onChange={() => toggleCast(c.id)} />
                    {c.name}
                  </label>
                );
              })}
            </div>
          )}
          {errors.character_ids && <p id={`${castId}-err`} className="mt-1 text-xs text-danger">{errors.character_ids}</p>}
        </fieldset>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button type="submit" loading={busy}>{scene ? "Save scene" : "Add scene"}</Button>
        </div>
      </form>
    </Dialog>
  );
}
