"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, FormError } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { focusFirstError, splitErrors } from "@/lib/forms";
import type { Project } from "@/lib/types";

/** "New project" dialog. Opens the new project's workspace when created, unless `onCreated`
 * is given (then the caller decides, e.g. to select it in a form). */
export function CreateProjectDialog({ open, onOpenChange, onCreated }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (project: Project) => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const formRef = useRef<HTMLFormElement>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const close = (next: boolean) => {
    if (!next) {
      setTitle("");
      setDescription("");
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
    setBusy(true);
    setErrors({});
    setFormError(null);
    try {
      const { project } = await api.projects.create({ title: title.trim(), description: description.trim() });
      toast.success("Project created", project.title);
      close(false);
      if (onCreated) onCreated(project);
      else router.push(`/app/projects/${project.id}`);
    } catch (error) {
      const split = splitErrors(error, ["title", "description"]);
      setErrors(split.fieldErrors);
      setFormError(split.formError);
      focusFirstError(formRef.current);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={close} title="New project" description="A project holds one story: its characters, scenes, assets and generations.">
      <form ref={formRef} onSubmit={submit} noValidate className="flex flex-col gap-4">
        <FormError message={formError} />
        <Field label="Title" required error={errors.title}>
          {(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} placeholder="e.g. The Lighthouse Keeper" autoFocus />}
        </Field>
        <Field label="Description" error={errors.description} help="Optional. What is it about, who is it for?">
          {(p) => <Textarea {...p} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={10000} rows={3} />}
        </Field>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={() => close(false)}>Cancel</Button>
          <Button type="submit" loading={busy}>Create project</Button>
        </div>
      </form>
    </Dialog>
  );
}
