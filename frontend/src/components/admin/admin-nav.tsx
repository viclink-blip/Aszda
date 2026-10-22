"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";

const LINKS = [
  { href: "/app/admin", label: "Overview" },
  { href: "/app/admin/users", label: "Users" },
  { href: "/app/admin/jobs", label: "Jobs" },
  { href: "/app/admin/usage", label: "Usage" },
  { href: "/app/admin/payments", label: "Payments" },
  { href: "/app/admin/pricing", label: "Pricing" },
  { href: "/app/admin/providers", label: "Providers" },
  { href: "/app/admin/audit", label: "Audit log" },
];

export function AdminNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Administration" className="-mx-4 mb-6 flex gap-1 overflow-x-auto border-b border-line px-4 sm:mx-0 sm:px-0">
      {LINKS.map((link) => {
        const active = pathname === link.href;
        return (
          <Link key={link.href} href={link.href} aria-current={active ? "page" : undefined}
            className={cn("-mb-px border-b-2 px-3 py-2.5 text-sm font-medium whitespace-nowrap",
              active ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg")}>
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
