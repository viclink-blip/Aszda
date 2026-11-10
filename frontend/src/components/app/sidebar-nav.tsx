"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { isActive, NAV_GROUPS } from "./nav-items";

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav aria-label="ASZDA workspace" className="flex flex-col gap-7">
      {NAV_GROUPS.map((group) => {
        const firstMatch = group.items.find((item) => isActive(pathname, item));
        return (
          <section key={group.label} aria-label={group.label}>
            <h2 className="mb-[-16px] px-3 text-[10px] font-bold uppercase tracking-[0.17em] text-[#70778e]">{group.label}</h2>
            <ul className="flex flex-col gap-1">
              {group.items.map((item) => {
                const active = item === firstMatch;
                const Icon = item.icon;
                return (
                  <li key={item.label}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex min-h-10 items-center gap-3 rounded-[10px] px-3 py-[11px] text-left text-sm transition-colors",
                        active ? "bg-[#211b34] text-white" : "text-[#aeb3c5] hover:bg-[#211b34] hover:text-white",
                      )}
                    >
                      <Icon className="h-[17px] w-[17px] shrink-0" aria-hidden />
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
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
