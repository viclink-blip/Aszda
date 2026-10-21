"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

interface CreditsValue {
  /** null until loaded (or if loading failed) — never a guessed number. */
  balance: number | null;
  refresh: () => Promise<void>;
}

const CreditsContext = createContext<CreditsValue | null>(null);

/** Shares the signed-in user's credit balance between the header and pages. */
export function CreditsProvider({ children }: { children: React.ReactNode }) {
  const [balance, setBalance] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const { account } = await api.me.credits({ limit: 1 });
      setBalance(account.balance);
    } catch {
      // Keep the last known value; pages show their own errors.
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    api.me.credits({ limit: 1 })
      .then(({ account }) => !cancelled && setBalance(account.balance))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo(() => ({ balance, refresh }), [balance, refresh]);
  return <CreditsContext.Provider value={value}>{children}</CreditsContext.Provider>;
}

export function useCredits(): CreditsValue {
  const ctx = useContext(CreditsContext);
  if (!ctx) throw new Error("useCredits must be used inside <CreditsProvider>");
  return ctx;
}
