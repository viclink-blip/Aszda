import { ArrowRight, Check } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { PlannedBadge } from "@/components/ui/badge";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "AI Film Director (planned)" };

/** Each step of the planned Director, and what can be done today instead. */
const STEPS = [
  { title: "Story", text: "Start from a sentence, a brief or a full story.", today: { label: "Project description", href: "/app/projects" } },
  { title: "Concept", text: "Logline, tone, genre and possible directions.", today: { label: "Script Studio → Story concept", href: "/app/studio/script" } },
  { title: "Script", text: "A screenplay draft written for short, visual scenes.", today: { label: "Script Studio → Script draft", href: "/app/studio/script" } },
  { title: "Characters", text: "A cast with consistent visual descriptions and reference images.", today: { label: "Project → Characters", href: "/app/projects" } },
  { title: "Scenes", text: "The script broken into scenes with shots, dialogue and lengths.", today: { label: "Script Studio → Scene breakdown", href: "/app/studio/script" } },
  { title: "Storyboard", text: "Ordered scenes you can review and rearrange.", today: { label: "Project → Storyboard", href: "/app/projects" } },
  { title: "Review", text: "Approve each step before anything costs credits.", today: null },
  { title: "Generation", text: "Video, animation and voice for every scene, tracked in one place.", today: { label: "Video, Animation and Voice studios", href: "/app/studio/video" } },
  { title: "Assembly", text: "Scenes, voice and music joined into one exported film.", today: null },
];

export default function DirectorPage() {
  return (
    <>
      <PageHeader
        eyebrow="Planned"
        title={<span className="flex flex-wrap items-center gap-3">AI Film Director <PlannedBadge /></span>}
        description="A guided workflow that takes you from a story idea to a finished short film, one reviewed step at a time."
      />
      <Notice tone="warning" title="Not available yet" className="mb-8">
        The AI Film Director is planned and does not work yet. Nothing on this page generates anything. Most of the
        individual steps already exist as separate tools — they are linked below.
      </Notice>
      <ol className="flex flex-col gap-3">
        {STEPS.map((step, i) => (
          <li key={step.title} className="grid gap-3 rounded-xl border border-line bg-surface p-4 sm:grid-cols-[2.5rem_1fr_16rem] sm:items-center">
            <span className="font-mono text-sm text-subtle tabular-nums">{String(i + 1).padStart(2, "0")}</span>
            <div>
              <p className="font-medium text-fg">{step.title}</p>
              <p className="text-sm text-muted">{step.text}</p>
            </div>
            {step.today ? (
              <Link href={step.today.href} className="inline-flex items-center gap-1.5 text-sm text-fg hover:text-accent">
                <Check className="h-4 w-4 text-success" aria-hidden />
                <span className="flex-1">Today: {step.today.label}</span>
                <ArrowRight className="h-4 w-4 text-subtle" aria-hidden />
              </Link>
            ) : (
              <span className="text-sm text-subtle">Not available yet</span>
            )}
          </li>
        ))}
      </ol>
    </>
  );
}
