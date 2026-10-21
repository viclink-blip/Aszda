"use client";

/**
 * Who is signed in.
 *
 * On first load we try POST /api/auth/refresh: if the browser still has a valid
 * HttpOnly refresh cookie, that returns a fresh access token and the user.
 * The access token is kept in memory only (see lib/api.ts), so a page reload
 * always goes through this refresh step.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, refreshSession, setAccessToken, setSessionListener } from "./api";
import type { SessionResponse, User } from "./types";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  signIn: (email: string, password: string) => Promise<User>;
  signUp: (data: { email: string; password: string; display_name: string; accept_terms: boolean }) => Promise<User>;
  signOut: () => Promise<void>;
  /** Replace the stored user after a profile change or email verification. */
  setUser: (user: User) => void;
  /** Called after "sign out everywhere" or account deletion (server already ended the session). */
  clearSession: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUserState] = useState<User | null>(null);

  const applySession = useCallback((session: SessionResponse | null) => {
    if (session) {
      setAccessToken(session.access_token);
      setUserState(session.user);
      setStatus("authenticated");
    } else {
      setAccessToken(null);
      setUserState(null);
      setStatus("anonymous");
    }
  }, []);

  useEffect(() => {
    // Background refreshes in lib/api.ts report back here.
    setSessionListener(applySession);
    let cancelled = false;
    refreshSession().then((session) => {
      if (!cancelled) applySession(session);
    });
    return () => {
      cancelled = true;
    };
  }, [applySession]);

  const signIn = useCallback(async (email: string, password: string) => {
    const session = await api.auth.login(email, password);
    applySession(session);
    return session.user;
  }, [applySession]);

  const signUp = useCallback<AuthContextValue["signUp"]>(async (data) => {
    const session = await api.auth.register(data);
    applySession(session);
    return session.user;
  }, [applySession]);

  const signOut = useCallback(async () => {
    try {
      await api.auth.logout();
    } finally {
      applySession(null);
    }
  }, [applySession]);

  const setUser = useCallback((next: User) => setUserState(next), []);
  const clearSession = useCallback(() => applySession(null), [applySession]);

  const value = useMemo(
    () => ({ status, user, signIn, signUp, signOut, setUser, clearSession }),
    [status, user, signIn, signUp, signOut, setUser, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
