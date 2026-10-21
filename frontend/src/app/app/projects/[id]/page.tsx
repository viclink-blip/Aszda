import type { Metadata } from "next";
import { Suspense } from "react";
import { ProjectWorkspace } from "@/components/projects/project-workspace";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Project" };

export default function ProjectPage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <ProjectWorkspace />
    </Suspense>
  );
}
