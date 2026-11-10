import type { Metadata } from "next";
import { Suspense } from "react";
import { ProjectsView } from "@/components/projects/projects-view";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Projects" };

export default function ProjectsPage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <ProjectsView />
    </Suspense>
  );
}
