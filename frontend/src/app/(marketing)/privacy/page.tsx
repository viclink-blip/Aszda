import type { Metadata } from "next";
import { DraftNotice } from "@/components/marketing/draft-notice";
import { PageHero } from "@/components/marketing/section";
import { CONTACT_EMAIL } from "@/lib/product";

export const metadata: Metadata = { title: "Privacy Policy" };

export default function PrivacyPage() {
  return (
    <>
      <PageHero eyebrow="Legal" title="Privacy Policy" />
      <div className="container-page pb-20">
        <div className="max-w-3xl">
          <DraftNotice />
          <div className="prose-aszda">
            <p>
              This policy explains what personal data ASZDA collects when you use ASZDA Studio, why we
              collect it, and the choices and rights you have. ASZDA is based in Kenya and processes
              personal data in line with the <strong>Kenya Data Protection Act, 2019</strong>. We also
              serve users in other countries and aim to respect the data protection laws that apply to
              them, such as the GDPR for users in the European Economic Area and the UK.
            </p>

            <h2>1. Data we collect</h2>
            <ul>
              <li><strong>Account data:</strong> your email address, display name, password (stored only as a secure hash), preferred language and country if you provide them.</li>
              <li><strong>Content you create:</strong> projects, characters, scenes, prompts, uploaded files and generated results.</li>
              <li><strong>Usage and billing records:</strong> generation jobs, their status and usage, and your credit ledger.</li>
              <li><strong>Security data:</strong> sign-in sessions, IP addresses and device information used to protect your account, and an audit log of security-relevant actions.</li>
            </ul>

            <h2>2. How we use it</h2>
            <ul>
              <li>To provide the service: run generations you request and store your work.</li>
              <li>To keep your account secure and prevent abuse.</li>
              <li>To send essential emails, such as email verification and password resets.</li>
              <li>To understand overall usage and costs so we can improve ASZDA Studio.</li>
            </ul>
            <p>We do not sell your personal data.</p>

            <h2>3. AI providers</h2>
            <p>
              When you start a generation, the prompt, settings and any reference files needed for that
              request are sent to the AI provider that performs it — currently Anthropic (writing), OpenAI
              (voice) and Runway (video). These providers process the data under their own terms and
              privacy policies. Only send content you have the right to use.
            </p>

            <h2>4. International transfers</h2>
            <p>
              Our providers and hosting may be located outside Kenya. Where personal data is transferred
              abroad, we rely on appropriate safeguards as required by the Kenya Data Protection Act, 2019
              and other applicable laws.
            </p>

            <h2>5. How long we keep data</h2>
            <p>
              We keep your account and content while your account is active. When you delete your account
              from Settings, your account, projects and files are permanently deleted. Some limited records
              (for example security logs) may be kept longer where the law requires it.
            </p>

            <h2>6. Your rights</h2>
            <p>
              Subject to applicable law, you can ask to access, correct, delete or obtain a copy of your
              personal data, object to or restrict certain processing, and withdraw consent. You can update
              your profile and delete your account yourself in Settings. You may also complain to the Office
              of the Data Protection Commissioner (Kenya) or your local data protection authority.
            </p>

            <h2>7. Security</h2>
            <p>
              Passwords are hashed, sessions use secure, HttpOnly cookies and short-lived access tokens,
              and files are served through short-lived private links. No system is perfectly secure, but we
              work to protect your data.
            </p>

            <h2>8. Cookies</h2>
            <p>
              We use a strictly necessary cookie to keep you signed in. Your theme choice (light or dark) is
              stored in your browser. We do not use advertising cookies.
            </p>

            <h2>9. Children</h2>
            <p>ASZDA Studio is not intended for children under 18 without the involvement of a parent or guardian.</p>

            <h2>10. Contact</h2>
            <p>
              Questions about privacy: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> (placeholder
              address, to be replaced before launch).
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
