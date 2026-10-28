import { ArrowRight, Boxes, Check, Coins, Layers } from "lucide-react";
import Link from "next/link";
import { CtaBand } from "@/components/marketing/cta-band";
import { Section, SectionHeading } from "@/components/marketing/section";
import { WorkflowBoard } from "@/components/marketing/workflow-board";
import { PlannedBadge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { PLANNED, PROVIDERS, STUDIOS } from "@/lib/product";

export default function HomePage() {
  return (
    <>
      {/* Hero */}
      <div className="container-page grid items-center gap-12 py-14 sm:py-20 lg:grid-cols-[1.1fr_1fr] lg:py-28">
        <div>
          <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">ASZDA Studio</p>
          <h1 className="mt-4 font-display text-5xl leading-[1.02] font-semibold tracking-tight text-fg sm:text-6xl lg:text-7xl">
            Imagine It.
            <br />
            <span className="text-brand">Create It.</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
            ASZDA Studio turns your ideas into video, animation, voice and AI-film workflows. Plan the
            story, shape characters and scenes, then generate with leading AI providers — all in one
            organised workspace.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <ButtonLink href="/sign-up" size="lg">
              Start creating <ArrowRight className="h-4 w-4" aria-hidden />
            </ButtonLink>
            <ButtonLink href="/how-it-works" size="lg" variant="outline">See how it works</ButtonLink>
          </div>
          <p className="mt-5 text-sm text-subtle">Designed to be clear for first-time creators and efficient for experienced teams.</p>
        </div>
        <WorkflowBoard />
      </div>

      {/* Studios */}
      <Section>
        <SectionHeading eyebrow="What you can make" title="Four studios, one project">
          Every studio saves its results into your projects, so scripts, characters, clips and voice
          stay together instead of scattered across tools.
        </SectionHeading>
        <div className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-2">
          {STUDIOS.map(({ slug, name, icon: Icon, summary, provider }) => (
            <div key={slug} className="flex flex-col bg-surface p-6 sm:p-8">
              <Icon className="h-6 w-6 text-accent" aria-hidden />
              <h3 className="mt-5 font-display text-xl font-semibold text-fg">{name}</h3>
              <p className="mt-2 flex-1 text-muted">{summary}</p>
              <p className="mt-5 font-mono text-xs text-subtle">Powered by {provider}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* Workspace */}
      <Section>
        <div className="grid gap-12 lg:grid-cols-2">
          <SectionHeading eyebrow="Organised from the start" title="A real production workspace">
            Projects hold your characters with reference images, a storyboard of ordered scenes with
            shot notes, dialogue and durations, every uploaded and generated asset, and the history of
            each generation.
          </SectionHeading>
          <ul className="grid gap-4 self-end">
            {[
              { icon: Layers, title: "Storyboard", text: "Ordered scenes with notes, dialogue, duration and the characters in each." },
              { icon: Boxes, title: "Assets", text: "Images, video, audio and text in one place, with private, short-lived links." },
              { icon: Coins, title: "Transparent credits", text: "See the estimated credits before you generate. Failed or cancelled jobs are refunded." },
            ].map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-4 rounded-xl border border-line bg-surface p-5">
                <Icon className="mt-0.5 h-5 w-5 shrink-0 text-accent" aria-hidden />
                <div>
                  <p className="font-medium text-fg">{title}</p>
                  <p className="mt-1 text-sm text-muted">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </Section>

      {/* Providers */}
      <Section>
        <SectionHeading eyebrow="Provider-independent" title="Leading AI providers, one studio">
          ASZDA does not train its own models. It works with leading AI providers through a
          provider-independent layer, so the best tool for each job can be used — and swapped — without
          changing how you work.
        </SectionHeading>
        <ul className="mt-10 grid gap-4 md:grid-cols-3">
          {PROVIDERS.map(({ name, role, icon: Icon }) => (
            <li key={name} className="rounded-xl border border-line bg-surface p-5">
              <Icon className="h-5 w-5 text-muted" aria-hidden />
              <p className="mt-4 font-medium text-fg">{name}</p>
              <p className="mt-1 text-sm text-muted">{role}</p>
            </li>
          ))}
        </ul>
      </Section>

      {/* Roadmap */}
      <Section>
        <SectionHeading eyebrow="Roadmap" title="Where ASZDA is going">
          These are planned and not available yet. We will only switch them on when they really work.
        </SectionHeading>
        <ul className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PLANNED.map(({ name, summary, icon: Icon }) => (
            <li key={name} className="rounded-xl border border-dashed border-line-strong p-5">
              <div className="flex items-center justify-between">
                <Icon className="h-5 w-5 text-muted" aria-hidden />
                <PlannedBadge />
              </div>
              <p className="mt-4 font-medium text-fg">{name}</p>
              <p className="mt-1 text-sm text-muted">{summary}</p>
            </li>
          ))}
        </ul>
        <p className="mt-8 flex items-center gap-2 text-sm text-muted">
          <Check className="h-4 w-4 text-success" aria-hidden />
          Want the details? Read <Link href="/features" className="text-accent underline underline-offset-4">all features</Link>.
        </p>
      </Section>

      <CtaBand />
    </>
  );
}
