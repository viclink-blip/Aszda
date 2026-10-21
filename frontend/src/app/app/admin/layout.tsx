"use client";

import { AdminNav } from "@/components/admin/admin-nav";
import { RequireAdmin } from "@/components/app/require-auth";
import { PageHeader } from "@/components/ui/page-header";

/** Admin pages. The API checks the admin role on every request; this guard only hides the UI. */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAdmin>
      <PageHeader eyebrow="Administration" title="Admin" description="Every change made here is recorded in the audit log." />
      <AdminNav />
      {children}
    </RequireAdmin>
  );
}
