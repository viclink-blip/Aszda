import {
  Clapperboard,
  Coins,
  FolderKanban,
  History,
  LayoutDashboard,
  type LucideIcon,
  PenLine,
  Settings,
  Shield,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Match only this exact path (used for /app so it is not active everywhere). */
  exact?: boolean;
}

export interface NavGroup {
  label?: string;
  items: NavItem[];
  adminOnly?: boolean;
}

/**
 * Client navigation for the ASZDA workspace.
 *
 * Each item intentionally points to an existing, working route. Features that
 * need new backend capabilities (film library, notifications, global character
 * and scene libraries) will be added when their data flows are implemented.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { href: "/app", label: "Dashboard", icon: LayoutDashboard, exact: true },
      { href: "/app/director", label: "Film Studio", icon: Clapperboard },
      { href: "/app/studio/script", label: "Story Studio", icon: PenLine },
      { href: "/app/projects", label: "My Projects", icon: FolderKanban },
    ],
  },
  {
    label: "Account",
    items: [
      { href: "/app/credits", label: "Wallet & Credits", icon: Coins },
      { href: "/app/generations", label: "Usage History", icon: History },
      { href: "/app/settings", label: "Settings", icon: Settings },
    ],
  },
  {
    label: "Administration",
    adminOnly: true,
    items: [{ href: "/app/admin", label: "Admin", icon: Shield }],
  },
];

export function isActive(pathname: string, item: NavItem): boolean {
  return item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`);
}
