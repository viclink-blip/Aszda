"use client";

import { AudioLines, Copy, Film, PenLine, Trash2, Wand2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Field, FormError } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { focusFirstError, splitErrors } from "@/lib/forms";
import { formatDate, PROJECT_STATUS_LABELS } from "@/lib/format";
import type { ProjectStatus } from "@/lib/types";
import type { ProjectTabProps } from "./project-workspace";

export function OverviewTab({ detail, update }: ProjectTabProps) {
  const { project } = detail;
  const router = useRouter();
  const toast = useToast();
  const formRef = useRef<HTMLFormElement>(null);
  const [form, setForm] = useState({ title: project.title, description: project.description, status: project.status });
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [duplicating, setDuplicating] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const dirty = form.title !== project.title || form.description !== project.description || form.status !== project.status;

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.title.trim()) {
      setErrors({ title: "The title cannot be empty." });
      focusFirstError(formRef.current);
      return;
    }
    setSaving(true);
    setErrors({});
    setFormError(null);
    try {
      const { project: saved } = await api.projects.update(project.id, {
        title: form.title.trim(), description: form.description, status: form.status,
      });
      // The update response has no counts; keep the ones we already have.
      update((d) => ({ ...d, project: { ...d.project, ...saved } }));
      setForm({ title: saved.title, description: saved.description, status: saved.status });
      toast.success("Project saved");
    } catch (error) {
      const split = splitErrors(error, ["title", "description", "status"]);
      setErrors(split.fieldErrors);
      setFormError(split.formError);
      focusFirstError(formRef.current);
    } finally {
      setSaving(false);
    }
  };

  const duplicate = async () => {
    setDuplicating(true);
    try {
      const { project: copy } = await api.projects.duplicate(project.id);
      toast.success("Project duplicated", "Text, characters and scenes were copied. Media files were not.");
      router.push(`/app/projects/${copy.id}`);
    } catch (error) {
      toast.error("Could not duplicate", errorMessage(error));
    } finally {
      setDuplicating(false);
    }
  };

  const remove = async () => {
    await api.projects.remove(project.id).catch((error) => {
      throw new Error(errorMessage(error));
    });
    toast.success("Project deleted");
    router.replace("/app/projects");
  };

  const studioLinks = [
    { href: `/app/studio/script?project=${project.id}`, label: "Write", icon: PenLine },
    { href: `/app/studio/video?project=${project.id}`, label: "Video", icon: Film },
    { href: `/app/studio/animation?project=${project.id}`, label: "Animate", icon: Wand2 },
    { href: `/app/studio/voice?project=${project.id}`, label: "Voice", icon: AudioLines },
  ];

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
      <Card>
        <CardHeader title="Details" />
        <CardBody>
          <form ref={formRef} onSubmit={save} noValidate className="flex flex-col gap-4">
            <FormError message={formError} />
            <Field label="Title" required error={errors.title}>
              {(p) => <Input {...p} maxLength={120} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />}
            </Field>
            <Field label="Description" error={errors.description} help="The story, audience, tone — anything that helps you and your collaborators.">
              {(p) => <Textarea {...p} rows={5} maxLength={10000} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />}
            </Field>
            <Field label="Status" error={errors.status} className="sm:max-w-xs">
              {(p) => (
                <Select {...p} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as ProjectStatus })}>
                  {Object.entries(PROJECT_STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </Select>
              )}
            </Field>
            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              <p className="text-xs text-subtle">Created {formatDate(project.created_at)} · updated {formatDate(project.updated_at, true)}</p>
              <Button type="submit" loading={saving} disabled={!dirty}>Save changes</Button>
            </div>
          </form>
        </CardBody>
      </Card>

      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader title="Create for this project" />
          <CardBody className="grid grid-cols-2 gap-2">
            {studioLinks.map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href} className="flex items-center gap-2 rounded-lg border border-line px-3 py-2.5 text-sm text-fg hover:bg-surface-2">
                <Icon className="h-4 w-4 text-accent" aria-hidden /> {label}
              </Link>
            ))}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Project actions" />
          <CardBody className="flex flex-col gap-3">
            <Button variant="outline" onClick={duplicate} loading={duplicating} className="justify-start">
              <Copy className="h-4 w-4" aria-hidden /> Duplicate project
            </Button>
            <p className="text-xs text-subtle">Copies the text, characters and scenes. Images, videos and audio are not copied.</p>
            <hr className="border-line" />
            <Button variant="outline" onClick={() => setDeleting(true)} className="justify-start text-danger">
              <Trash2 className="h-4 w-4" aria-hidden /> Delete project
            </Button>
          </CardBody>
        </Card>
      </div>

      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title="Delete this project?"
        description={<>This permanently deletes <strong className="text-fg">{project.title}</strong>, its characters, scenes and all of its files. This cannot be undone.</>}
        confirmText={project.title.trim()}
        confirmLabel="Delete forever"
        destructive
        onConfirm={remove}
      />
    </div>
  );
}
