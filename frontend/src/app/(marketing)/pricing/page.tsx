import type { Metadata } from "next";
import { PublicPricing } from "@/components/billing/public-pricing";
import { CtaBand } from "@/components/marketing/cta-band";
import { PageHero, Section } from "@/components/marketing/section";

export const metadata: Metadata = { title: "Pricing" };

const HOW_CREDITS_WORK = [
  { title: "Estimate first", text: "Before you generate, ASZDA shows how many credits the job can cost at most." },
  { title: "Reserve while running", text: "Those credits are held while the provider works, so you never go below zero." },
  { title: "Pay for what was used", text: "When the job finishes, any unused part of the reservation is returned." },
  { title: "Refunds on failure", text: "If a job fails or you cancel it, the reserved credits come back in full." },
];

export default function PricingPage() {
  return (
    <>
      <PageHero eyebrow="Pricing" title="Simple plans in US dollars">
        Pick a monthly plan, and top up with credit packages whenever you need more. Prices are in US dollars;
        Kenyan shilling amounts are shown only as a guide.
      </PageHero>
      <Section>
        <PublicPricing />
        <h2 className="mt-16 font-display text-2xl font-semibold text-fg">How credits work</h2>
        <ol className="mt-6 grid gap-4 sm:grid-cols-2">
          {HOW_CREDITS_WORK.map((item, i) => (
            <li key={item.title} className="rounded-xl border border-line bg-surface p-5">
              <span className="font-mono text-xs text-subtle">Step {i + 1}</span>
              <p className="mt-2 font-medium text-fg">{item.title}</p>
              <p className="mt-1 text-sm text-muted">{item.text}</p>
            </li>
          ))}
        </ol>
      </Section>
      <CtaBand />
    </>
  );
}
