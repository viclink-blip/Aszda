"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, FormError } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { focusFirstError, splitErrors } from "@/lib/forms";
import type { Project } from "@/lib/types";

/** Create a film project with its creative brief saved on the project. */
export function CreateProjectDialog({ open, onOpenChange, onCreated }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (project: Project) => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const formRef = useRef<HTMLFormElement>(null);
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [filmStyle, setFilmStyle] = useState("cinematic");
  const [duration, setDuration] = useState("5");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const close = (next: boolean) => {
    if (!next) {
      setTitle("");
      setIdea("");
      setFilmStyle("cinematic");
      setDuration("5");
      setErrors({});
      setFormError(null);
    }
    onOpenChange(next);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim()) {
      setErrors({ title: "Give your project a title." });
      focusFirstError(formRef.current);
      return;
    }
    if (!idea.trim()) {
      setErrors({ idea: "Describe the film you want to create." });
      focusFirstError(formRef.current);
      return;
    }
    setBusy(true);
    setErrors({});
    setFormError(null);
    try {
      const { project } = await api.projects.create({
        title: title.trim(),
        description: idea.trim(),
        brief: {
          film_style: filmStyle,
          target_duration_minutes: Number(duration),
        },
      });
      toast.success("Project created", project.title);
      close(false);
      if (onCreated) onCreated(project);
      else router.push(`/app/projects/${project.id}`);
    } catch (error) {
      const split = splitErrors(error, ["title", "description", "brief"]);
      setErrors(split.fieldErrors);
      setFormError(split.formError);
      focusFirstError(formRef.current);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={close} title="Create a film project" description="Start with your idea. You can develop the screenplay, characters and scenes inside the project.">
      <form ref={formRef} onSubmit={submit} noValidate className="flex flex-col gap-4">
        <FormError message={formError} />
        <Field label="Project title" required error={errors.title}>
          {(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} placeholder="e.g. The Last Arrival" autoFocus />}
        </Field>
        <Field label="Your film idea" required error={errors.idea ?? errors.description} help="Describe the story you want ASZDA to help you create.">
          {(p) => <Textarea {...p} value={idea} onChange={(e) => setIdea(e.target.value)} maxLength={10000} rows={4} placeholder="What happens in your film? Who is it about?" />}
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Film style">
            {(p) => (
              <Select {...p} value={filmStyle} onChange={(e) => setFilmStyle(e.target.value)}>
                <option value="cinematic">Cinematic</option>
                <option value="animation">Animation</option>
                <option value="documentary">Documentary</option>
                <option value="fantasy">Fantasy</option>
                <option value="science_fiction">Science fiction</option>
              </Select>
            )}
          </Field>
          <Field label="Target film duration">
            {(p) => (
              <Select {...p} value={duration} onChange={(e) => setDuration(e.target.value)}>
                <option value="1">About 1 minute</option>
                <option value="3">About 3 minutes</option>
                <option value="5">About 5 minutes</option>
                <option value="10">About 10 minutes</option>
                <option value="15">About 15 minutes</option>
              </Select>
            )}
          </Field>
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={() => close(false)}>Cancel</Button>
          <Button type="submit" loading={busy}>Create project</Button>
        </div>
      </form>
    </Dialog>
  );
}
