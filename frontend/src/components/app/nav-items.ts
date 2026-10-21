import {
  AudioLines,
  Clapperboard,
  Coins,
  FolderKanban,
  History,
  LayoutDashboard,
  type LucideIcon,
  PenLine,
  Settings,
  Shield,
  Film,
  Wand2,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  planned?: boolean;
  /** Match only this exact path (used for /app so it is not active everywhere). */
  exact?: boolean;
}

export interface NavGroup {
  label?: string;
  items: NavItem[];
  adminOnly?: boolean;
}

export const NAV_GROUPS: NavGroup[] = [
  {
    items: [
      { href: "/app", label: "Dashboard", icon: LayoutDashboard, exact: true },
      { href: "/app/projects", label: "Projects", icon: FolderKanban },
      { href: "/app/generations", label: "Generations", icon: History },
    ],
  },
  {
    label: "Studios",
    items: [
      { href: "/app/studio/script", label: "Script", icon: PenLine },
      { href: "/app/studio/video", label: "Video", icon: Film },
      { href: "/app/studio/animation", label: "Animation", icon: Wand2 },
      { href: "/app/studio/voice", label: "Voice", icon: AudioLines },
      { href: "/app/director", label: "AI Film Director", icon: Clapperboard, planned: true },
    ],
  },
  {
    label: "Account",
    items: [
      { href: "/app/credits", label: "Credits", icon: Coins },
      { href: "/app/settings", label: "Settings", icon: Settings },
    ],
  },
  {
    label: "Admin",
    adminOnly: true,
    items: [{ href: "/app/admin", label: "Administration", icon: Shield }],
  },
];

export function isActive(pathname: string, item: NavItem): boolean {
  return item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`);
}
