"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { isActive, NAV_GROUPS } from "./nav-items";

/** Prototype-aligned navigation shared by the desktop sidebar and mobile drawer. */
export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <nav aria-label="ASZDA workspace" className="flex flex-col gap-7">
      {NAV_GROUPS.filter((group) => !group.adminOnly || user?.role === "admin").map((group) => {
        const firstMatch = group.items.find((item) => isActive(pathname, item));
        return (
          <section key={group.label} aria-label={group.label}>
            <h2 className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.19em] text-subtle">{group.label}</h2>
            <ul className="flex flex-col gap-1">
              {group.items.map((item) => {
                const active = item === firstMatch;
                const Icon = item.icon;
                return (
                  <li key={`${item.label}:${item.href}`}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "group flex min-h-10 items-center gap-3 rounded-xl px-3 py-2 text-[13px] transition-all duration-150",
                        active
                          ? "bg-[linear-gradient(100deg,rgba(142,82,225,0.2),rgba(62,117,213,0.12))] font-semibold text-fg ring-1 ring-inset ring-accent/20"
                          : "text-muted hover:bg-surface-2 hover:text-fg",
                      )}
                    >
                      <Icon className={cn("h-[17px] w-[17px] shrink-0 transition-colors", active ? "text-accent" : "text-subtle group-hover:text-fg")} aria-hidden />
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      {item.planned && <span className="rounded-full border border-warning/30 px-1.5 py-0.5 text-[9px] font-semibold text-warning">Planned</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </nav>
  );
}
