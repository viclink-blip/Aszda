import type { Metadata } from "next";
import Link from "next/link";
import { DraftNotice } from "@/components/marketing/draft-notice";
import { PageHero } from "@/components/marketing/section";
import { CONTACT_EMAIL } from "@/lib/product";

export const metadata: Metadata = { title: "Terms of Service" };

export default function TermsPage() {
  return (
    <>
      <PageHero eyebrow="Legal" title="Terms of Service" />
      <div className="container-page pb-20">
        <div className="max-w-3xl">
          <DraftNotice />
          <div className="prose-aszda">
            <p>
              These terms are an agreement between you and ASZDA for your use of ASZDA Studio. By creating
              an account you agree to them and to our <Link href="/privacy">Privacy Policy</Link>.
            </p>

            <h2>1. Your account</h2>
            <p>
              Give accurate information, keep your password safe, and tell us if you think your account has
              been accessed without permission. You are responsible for activity on your account.
            </p>

            <h2>2. What ASZDA Studio does</h2>
            <p>
              ASZDA Studio helps you plan and generate creative content. Generation is performed by
              third-party AI providers through ASZDA&apos;s provider layer. AI output can be inaccurate,
              unexpected or similar to other content; review it before you use it. Features marked
              &quot;Planned&quot; are not available and may change.
            </p>

            <h2>3. Your content</h2>
            <p>
              You keep the rights you have in the prompts and files you provide. Subject to the providers&apos;
              terms and applicable law, ASZDA claims no ownership of the results you generate. You give
              ASZDA permission to store and process your content only as needed to run the service.
            </p>

            <h2>4. Acceptable use</h2>
            <ul>
              <li>Do not upload or generate content that is illegal, sexualises minors, harasses people, or infringes others&apos; rights.</li>
              <li>Do not impersonate real people or create deceptive content intended to mislead.</li>
              <li>Do not use another person&apos;s likeness or voice without their permission.</li>
              <li>Do not attempt to break, overload or bypass the security or limits of the service.</li>
            </ul>
            <p>We may suspend accounts that break these rules.</p>

            <h2>5. Credits</h2>
            <p>
              Generations use credits. Credits are reserved when a job starts; unused credits are returned
              when it finishes, and failed or cancelled jobs are refunded. Pricing and payments are not
              final and not active yet; we will publish clear terms before any payment is taken. Credits
              have no cash value unless the law requires otherwise.
            </p>

            <h2>6. Availability</h2>
            <p>
              We work to keep ASZDA Studio available, but providers can be unavailable and the service may
              change. To the extent permitted by law, the service is provided &quot;as is&quot;.
            </p>

            <h2>7. Liability</h2>
            <p>
              To the extent permitted by law, ASZDA is not liable for indirect or consequential losses. Nothing
              in these terms limits rights you have under consumer protection laws that cannot be excluded.
            </p>

            <h2>8. Ending the agreement</h2>
            <p>You can delete your account at any time in Settings. This permanently removes your projects and files.</p>

            <h2>9. Governing law</h2>
            <p>
              These terms are governed by the laws of Kenya, including the Kenya Data Protection Act, 2019
              for personal data. If you live outside Kenya, you may also benefit from mandatory protections
              of the law where you live.
            </p>

            <h2>10. Contact</h2>
            <p>
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> (placeholder address, to be replaced before launch).
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
