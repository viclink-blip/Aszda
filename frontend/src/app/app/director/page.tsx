import type { Metadata } from "next";
import { Suspense } from "react";
import { DirectorView } from "@/components/director/director-view";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "AI Film Director" };

export default function DirectorPage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <DirectorView />
    </Suspense>
  );
}
