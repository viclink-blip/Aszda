import {
  LayoutDashboard,
  Clapperboard,
  BookOpen,
  Users,
  PanelsTopLeft,
  Film,
  FolderKanban,
  Wallet,
  History,
  Settings,
  Shield,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  exact?: boolean;
  planned?: boolean;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
  adminOnly?: boolean;
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
      { href: "/app/generations", label: "My Films", icon: Film },
      { href: "/app/projects", label: "My Projects", icon: FolderKanban },
    ],
  },
  {
    label: "Account",
    items: [
      { href: "/app/credits", label: "Wallet & Credits", icon: Wallet },
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
  return item.exact
    ? pathname === item.href
    : pathname === item.href || pathname.startsWith(`${item.href}/`);
}
