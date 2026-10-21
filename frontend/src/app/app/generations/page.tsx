import type { Metadata } from "next";
import { Suspense } from "react";
import { GenerationsView } from "@/components/generation/generations-view";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Generations" };

export default function GenerationsPage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <GenerationsView />
    </Suspense>
  );
}
