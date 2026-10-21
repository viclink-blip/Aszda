"use client";

import { Coins } from "lucide-react";
import Link from "next/link";
import { formatNumber } from "@/lib/format";
import { useCredits } from "./credits-context";

/** Current balance from the API; shows "—" until it has loaded. */
export function CreditsPill() {
  const { balance } = useCredits();
  return (
    <Link
      href="/app/credits"
      className="inline-flex h-9 items-center gap-2 rounded-lg border border-line px-3 text-sm text-fg hover:bg-surface-2"
      aria-label={balance === null ? "Credits" : `${balance} credits`}
    >
      <Coins className="h-4 w-4 text-accent" aria-hidden />
      <span className="font-medium tabular-nums">{balance === null ? "—" : formatNumber(balance)}</span>
      <span className="hidden text-muted sm:inline">credits</span>
    </Link>
  );
}
