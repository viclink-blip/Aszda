"use client";

import { Coins, LogOut, Settings } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/lib/auth";

function initials(name: string, email: string): string {
  const source = name.trim() || email;
  const parts = source.split(/\s+/).filter(Boolean);
  return (parts.length > 1 ? parts[0][0] + parts[1][0] : source.slice(0, 2)).toUpperCase();
}

export function UserMenu() {
  const { user, signOut } = useAuth();
  const router = useRouter();
  const toast = useToast();
  if (!user) return null;

  const doSignOut = async () => {
    try {
      await signOut();
    } catch {
      // Even if the server call failed, the local session is cleared.
    }
    toast.success("Signed out");
    router.replace("/sign-in");
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex h-9 w-9 items-center justify-center rounded-full bg-fg text-xs font-semibold text-bg"
        aria-label="Account menu"
      >
        {initials(user.display_name, user.email)}
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel className="text-fg">
          <span className="block truncate text-sm font-medium">{user.display_name || "Your account"}</span>
          <span className="block truncate text-xs text-subtle">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/app/settings"><Settings className="h-4 w-4 text-subtle" aria-hidden /> Settings</Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/app/credits"><Coins className="h-4 w-4 text-subtle" aria-hidden /> Credits</Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={doSignOut}>
          <LogOut className="h-4 w-4 text-subtle" aria-hidden /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
