import { Mail } from "lucide-react";
import type { Metadata } from "next";
import { PageHero, Section } from "@/components/marketing/section";
import { Notice } from "@/components/ui/notice";
import { CONTACT_EMAIL } from "@/lib/product";

export const metadata: Metadata = { title: "Contact" };

export default function ContactPage() {
  return (
    <>
      <PageHero eyebrow="Contact" title="Talk to the ASZDA team">
        Questions, feedback, partnership ideas or a problem with your account — email us and a person
        will read it.
      </PageHero>
      <Section>
        <div className="max-w-xl">
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="flex items-center gap-4 rounded-2xl border border-line bg-surface p-6 hover:border-line-strong"
          >
            <span className="flex h-11 w-11 items-center justify-center rounded-full bg-accent-soft text-accent">
              <Mail className="h-5 w-5" aria-hidden />
            </span>
            <span>
              <span className="block text-sm text-muted">Email</span>
              <span className="block font-medium text-fg">{CONTACT_EMAIL}</span>
            </span>
          </a>
          <Notice tone="warning" title="Placeholder address" className="mt-6">
            This is a placeholder email address and will be replaced with the real ASZDA contact address
            before launch. There is no contact form yet, so nothing is sent from this page.
          </Notice>
        </div>
      </Section>
    </>
  );
}
