import type { Metadata } from "next";
import { CtaBand } from "@/components/marketing/cta-band";
import { PageHero, Section } from "@/components/marketing/section";

export const metadata: Metadata = { title: "About" };

const PRINCIPLES = [
  { title: "Honest by default", text: "We show real numbers from your account, label planned features as planned, and never pretend a generation happened." },
  { title: "Provider-independent", text: "ASZDA does not own proprietary AI models. We work with leading providers and can change them as the field moves." },
  { title: "Beginner-friendly, production-minded", text: "Clear language and good defaults for first-time creators, with the structure professionals expect." },
  { title: "Built for everyone, everywhere", text: "ASZDA is designed for creators across Africa and around the world, with privacy treated as a requirement." },
];

export default function AboutPage() {
  return (
    <>
      <PageHero eyebrow="About ASZDA" title="An independent creative-technology company">
        ASZDA builds tools that help people turn ideas into stories you can watch and hear. ASZDA Studio
        is our first product: one workspace for video, animation, voice and AI-film workflows.
      </PageHero>
      <Section>
        <div className="grid gap-10 lg:grid-cols-[1fr_1.4fr]">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-fg">What we believe</h2>
          <dl className="grid gap-8 sm:grid-cols-2">
            {PRINCIPLES.map((p) => (
              <div key={p.title}>
                <dt className="font-medium text-fg">{p.title}</dt>
                <dd className="mt-2 text-muted">{p.text}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Section>
      <Section>
        <div className="max-w-2xl">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-fg">Where we are</h2>
          <p className="mt-4 text-lg leading-relaxed text-muted">
            ASZDA Studio is early. Script, video, animation and voice studios work today with connected
            providers. The AI Film Director, image generation, export and payments are planned. We
            would rather ship fewer things that work than many that do not.
          </p>
        </div>
      </Section>
      <CtaBand />
    </>
  );
}
