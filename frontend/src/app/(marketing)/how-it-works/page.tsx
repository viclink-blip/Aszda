import type { Metadata } from "next";
import { CtaBand } from "@/components/marketing/cta-band";
import { PageHero, Section } from "@/components/marketing/section";
import { PlannedBadge } from "@/components/ui/badge";

export const metadata: Metadata = { title: "How it works" };

const STEPS = [
  {
    title: "Create an account and a project",
    text: "A project is the home for one story, ad or film: its characters, storyboard, assets and generations.",
  },
  {
    title: "Develop the story",
    text: "Use the Script Studio to turn your idea into a concept, a script draft, character sheets or a scene breakdown.",
  },
  {
    title: "Plan characters and scenes",
    text: "Add characters with reference images, then build the storyboard: ordered scenes with shot notes, dialogue and durations.",
  },
  {
    title: "Check the cost, then generate",
    text: "Pick a model and settings. ASZDA shows the estimated credits before you submit, then reserves them while the job runs.",
  },
  {
    title: "Follow progress and review results",
    text: "Jobs update live. Finished clips, audio and text are saved to your project. Failed or cancelled jobs return their credits.",
  },
];

export default function HowItWorksPage() {
  return (
    <>
      <PageHero eyebrow="How it works" title="From a sentence to scenes you can watch">
        ASZDA Studio keeps the creative process in order: plan first, generate with intent, and keep every
        result organised.
      </PageHero>
      <Section>
        <ol className="relative grid gap-6">
          {STEPS.map((step, index) => (
            <li key={step.title} className="grid gap-4 rounded-2xl border border-line bg-surface p-6 sm:grid-cols-[4rem_1fr]">
              <span className="font-mono text-2xl text-accent tabular-nums">{String(index + 1).padStart(2, "0")}</span>
              <div>
                <h2 className="font-display text-xl font-semibold text-fg">{step.title}</h2>
                <p className="mt-2 text-muted">{step.text}</p>
              </div>
            </li>
          ))}
          <li className="grid gap-4 rounded-2xl border border-dashed border-line-strong p-6 sm:grid-cols-[4rem_1fr]">
            <span className="font-mono text-2xl text-subtle tabular-nums">06</span>
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="font-display text-xl font-semibold text-fg">Assemble and export</h2>
                <PlannedBadge />
              </div>
              <p className="mt-2 text-muted">
                Joining scenes, voice and music into one exported film is planned, as part of the AI Film
                Director. Today you can download each generated asset individually.
              </p>
            </div>
          </li>
        </ol>
      </Section>
      <CtaBand />
    </>
  );
}
