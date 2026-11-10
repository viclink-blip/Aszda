import {
  LayoutDashboard,
  Clapperboard,
  BookOpen,
  Users,
  PanelsTopLeft,
  Film,
  Wallet,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  exact?: boolean;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { href: "/app", label: "Dashboard", icon: LayoutDashboard, exact: true },
      { href: "/app/director", label: "Film Studio", icon: Clapperboard },
      { href: "/app/studio/script", label: "Story Studio", icon: BookOpen },
      { href: "/app/projects", label: "Character Studio", icon: Users },
      { href: "/app/director", label: "Scene Preview", icon: PanelsTopLeft },
      { href: "/app/generations?kind=video", label: "My Films", icon: Film },
    ],
  },
  {
    label: "Account",
    items: [
      { href: "/app/credits", label: "Wallet & Plans", icon: Wallet },
      { href: "/app/settings", label: "Settings", icon: Settings },
    ],
  },
];

export function isActive(pathname: string, item: NavItem): boolean {
  const href = item.href.split("?")[0];
  return item.exact
    ? pathname === href
    : pathname === href || pathname.startsWith(`${href}/`);
}
