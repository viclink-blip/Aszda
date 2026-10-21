"use client";

import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/input";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";

/** Choose which project a generation belongs to (optional unless `required`). */
export function ProjectSelect({ value, onChange, required = false, help }: {
  value: string | null;
  onChange: (projectId: string | null) => void;
  required?: boolean;
  help?: string;
}) {
  const { data, loading } = useApi(() => api.projects.list({ limit: 100 }), []);
  const projects = data?.items ?? [];
  // A preselected project (from ?project=) might be beyond the first 100; keep it selectable.
  const missing = value && data && !projects.some((p) => p.id === value);

  return (
    <Field label="Project" required={required} help={help ?? "Results are saved to the project's assets. Optional."}>
      {(p) => (
        <Select {...p} value={value ?? ""} disabled={loading && !data} onChange={(e) => onChange(e.target.value || null)}>
          <option value="" disabled={required}>{required ? "Choose a project…" : "No project (personal library)"}</option>
          {missing && <option value={value}>Selected project</option>}
          {projects.map((project) => <option key={project.id} value={project.id}>{project.title}</option>)}
        </Select>
      )}
    </Field>
  );
}
