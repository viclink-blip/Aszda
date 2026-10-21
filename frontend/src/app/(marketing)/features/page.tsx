import type { Metadata } from "next";
import { CtaBand } from "@/components/marketing/cta-band";
import { PageHero, Section, SectionHeading } from "@/components/marketing/section";
import { Badge, PlannedBadge } from "@/components/ui/badge";
import { PLANNED, STUDIOS } from "@/lib/product";

export const metadata: Metadata = { title: "Features" };

const STUDIO_DETAILS: Record<string, string[]> = {
  script: [
    "Story concepts: logline, premise, tone and possible directions",
    "Script drafts in screenplay structure",
    "Character sheets with consistent visual descriptions",
    "Scene breakdowns with shots, dialogue and suggested lengths",
  ],
  video: [
    "Text-to-video from a written prompt",
    "Image-to-video using your reference image as the first frame",
    "Choice of model, aspect ratio and clip length",
    "Results saved to your project as video assets",
  ],
  animation: [
    "Pick a character from your project that has a reference image",
    "Describe the scene and movement",
    "ASZDA animates the still reference image into a short clip",
    "Honest scope: this is image-to-video, not full character rigging",
  ],
  voice: [
    "Narration and dialogue from text (up to 4,096 characters)",
    "Several voices, audio formats and speaking speed",
    "Speaking-style instructions on supported models",
    "No voice cloning: only the provider's built-in voices",
  ],
};

const WORKSPACE = [
  { title: "Projects", text: "Create, rename, duplicate, archive or delete projects; track their status." },
  { title: "Characters", text: "Names, descriptions and a reference image for consistent looks." },
  { title: "Storyboard", text: "Ordered scenes with descriptions, shot notes, dialogue, durations and cast." },
  { title: "Assets", text: "Upload or generate images, video, audio and text; preview, rename and delete." },
  { title: "Generation history", text: "Every job with live status, progress, result, cancel and retry." },
  { title: "Credits ledger", text: "A clear record of every credit reserved, charged, returned or granted." },
];

export default function FeaturesPage() {
  return (
    <>
      <PageHero eyebrow="Features" title="Everything you need to go from idea to clip">
        ASZDA Studio combines planning tools with AI generation. Here is exactly what works today, and
        what is still planned.
      </PageHero>

      <Section>
        <SectionHeading title="Studios" />
        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {STUDIOS.map(({ slug, name, icon: Icon, summary, provider }) => (
            <article key={slug} className="rounded-2xl border border-line bg-surface p-6">
              <div className="flex items-start justify-between gap-3">
                <Icon className="h-6 w-6 text-accent" aria-hidden />
                <Badge tone="success">Available</Badge>
              </div>
              <h3 className="mt-4 font-display text-xl font-semibold text-fg">{name}</h3>
              <p className="mt-2 text-muted">{summary}</p>
              <ul className="mt-4 space-y-2 text-sm text-muted">
                {STUDIO_DETAILS[slug].map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent" aria-hidden />
                    {item}
                  </li>
                ))}
              </ul>
              <p className="mt-5 font-mono text-xs text-subtle">Provider: {provider}</p>
            </article>
          ))}
        </div>
        <p className="mt-6 text-sm text-subtle">
          A studio can only generate when its provider is connected and priced by an administrator. If it
          is not, ASZDA shows it as unavailable instead of pretending.
        </p>
      </Section>

      <Section>
        <SectionHeading title="Project workspace" />
        <dl className="mt-10 grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
          {WORKSPACE.map((item) => (
            <div key={item.title} className="border-t border-line pt-4">
              <dt className="font-medium text-fg">{item.title}</dt>
              <dd className="mt-1 text-sm text-muted">{item.text}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section>
        <SectionHeading title="Planned">Not available yet — shown here so you know what is coming.</SectionHeading>
        <ul className="mt-10 grid gap-4 sm:grid-cols-2">
          {PLANNED.map(({ name, summary }) => (
            <li key={name} className="flex items-start justify-between gap-4 rounded-xl border border-dashed border-line-strong p-5">
              <div>
                <p className="font-medium text-fg">{name}</p>
                <p className="mt-1 text-sm text-muted">{summary}</p>
              </div>
              <PlannedBadge />
            </li>
          ))}
        </ul>
      </Section>
      <CtaBand />
    </>
  );
}
