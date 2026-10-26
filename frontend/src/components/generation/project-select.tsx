"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/input";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";

/** Choose which project a generation belongs to (optional unless `required`). */
export function ProjectSelect({ value, onChange, required = false, help, allowCreate = false }: {
  value: string | null;
  onChange: (projectId: string | null) => void;
  required?: boolean;
  help?: string;
  /** Show a "New project" button that creates one and selects it, without leaving the page. */
  allowCreate?: boolean;
}) {
  const { data, loading, reload } = useApi(() => api.projects.list({ limit: 100 }), []);
  const [creating, setCreating] = useState(false);
  const projects = data?.items ?? [];
  // A preselected project (from ?project=) might be beyond the first 100; keep it selectable.
  const missing = value && data && !projects.some((p) => p.id === value);

  return (
    <>
    <Field label="Project" required={required} help={help ?? "Results are saved to the project's assets. Optional."}
      aside={allowCreate ? (
        <Button type="button" size="sm" variant="ghost" onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" aria-hidden /> New project
        </Button>
      ) : undefined}>
      {(p) => (
        <Select {...p} value={value ?? ""} disabled={loading && !data} onChange={(e) => onChange(e.target.value || null)}>
          <option value="" disabled={required}>{required ? "Choose a project…" : "No project (personal library)"}</option>
          {missing && <option value={value}>Selected project</option>}
          {projects.map((project) => <option key={project.id} value={project.id}>{project.title}</option>)}
        </Select>
      )}
    </Field>
    {allowCreate && (
      <CreateProjectDialog open={creating} onOpenChange={setCreating}
        onCreated={(project) => { void reload().then(() => onChange(project.id)); }} />
    )}
    </>
  );
}
