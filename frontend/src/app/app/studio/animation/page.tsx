import type { Metadata } from "next";
import { Suspense } from "react";
import { AnimationStudio } from "@/components/generation/animation-studio";
import { PageSpinner } from "@/components/ui/spinner";

export const metadata: Metadata = { title: "Animation Studio" };

export default function AnimationStudioPage() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <AnimationStudio />
    </Suspense>
  );
}
