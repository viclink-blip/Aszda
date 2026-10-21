import type { Metadata } from "next";
import { CtaBand } from "@/components/marketing/cta-band";
import { PageHero, Section } from "@/components/marketing/section";
import { Notice } from "@/components/ui/notice";

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
      <PageHero eyebrow="Pricing" title="Pricing is not finalised yet">
        ASZDA Studio will use a credits-based model: you use credits when you generate, and each model
        costs a set number of credits based on what it produces. The plans and prices are still being
        designed, so we are not publishing any prices yet.
      </PageHero>
      <Section>
        <Notice tone="info" title="Payments are not active">
          You cannot buy credits yet. Credits shown in the app are granted by ASZDA during this early
          period. We will announce prices clearly before any payment is taken.
        </Notice>
        <h2 className="mt-12 font-display text-2xl font-semibold text-fg">How credits work</h2>
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
