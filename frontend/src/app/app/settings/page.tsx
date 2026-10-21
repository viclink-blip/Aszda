import type { Metadata } from "next";
import { DangerZone } from "@/components/account/danger-zone";
import { PasswordForm } from "@/components/account/password-form";
import { ProfileForm } from "@/components/account/profile-form";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" description="Your profile, password and account." />
      <div className="flex max-w-3xl flex-col gap-6">
        <ProfileForm />
        <PasswordForm />
        <DangerZone />
      </div>
    </>
  );
}
