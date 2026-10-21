import Link from "next/link";
import { StatusBadge } from "@/components/ui/badge";
import { formatRelative } from "@/lib/format";
import type { Project } from "@/lib/types";

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

function Count({ n, label }: { n: number | undefined; label: string }) {
  if (n === undefined) return null;
  return <span>{n} {label}{n === 1 ? "" : "s"}</span>;
}

export function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      href={`/app/projects/${project.id}`}
      className="group flex flex-col rounded-xl border border-line bg-surface p-5 transition-colors hover:border-line-strong"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="line-clamp-2 font-display font-semibold text-fg group-hover:text-accent">{project.title}</h3>
        <StatusBadge status={project.status} />
      </div>
      <p className="mt-2 line-clamp-2 min-h-10 text-sm text-muted">{project.description || "No description yet."}</p>
      <div className="mt-4 flex flex-wrap gap-x-3 gap-y-1 text-xs text-subtle">
        <Count n={project.scene_count} label="scene" />
        <Count n={project.character_count} label="character" />
        <Count n={project.asset_count} label="asset" />
        <span className="ml-auto">Updated {formatRelative(project.updated_at)}</span>
      </div>
    </Link>
  );
}

/** Compact row for lists (dashboard). */
export function ProjectRow({ project }: { project: Project }) {
  return (
    <Link href={`/app/projects/${project.id}`} className="flex items-center gap-3 px-5 py-3.5 hover:bg-surface-2/60">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">{project.title}</p>
        <p className="truncate text-xs text-subtle">
          {plural(project.scene_count ?? 0, "scene")} · {plural(project.character_count ?? 0, "character")} · updated {formatRelative(project.updated_at)}
        </p>
      </div>
      <StatusBadge status={project.status} />
    </Link>
  );
}
