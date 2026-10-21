"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { isActive, NAV_GROUPS } from "./nav-items";

/** The app's navigation links; used in the desktop sidebar and the mobile drawer. */
export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <nav aria-label="Studio" className="flex flex-col gap-6">
      {NAV_GROUPS.filter((g) => !g.adminOnly || user?.role === "admin").map((group, i) => (
        <div key={group.label ?? i}>
          {group.label && (
            <p className="mb-1.5 px-3 text-[11px] font-semibold tracking-wider text-subtle uppercase">{group.label}</p>
          )}
          <ul className="flex flex-col gap-0.5">
            {group.items.map((item) => {
              const active = isActive(pathname, item);
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                      active ? "bg-surface-2 font-medium text-fg" : "text-muted hover:bg-surface-2/60 hover:text-fg",
                    )}
                  >
                    <Icon className={cn("h-4 w-4 shrink-0", active ? "text-accent" : "text-subtle")} aria-hidden />
                    <span className="flex-1 truncate">{item.label}</span>
                    {item.planned && (
                      <span className="rounded border border-warning/30 px-1 text-[10px] font-medium text-warning">Planned</span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
