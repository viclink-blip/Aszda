"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { Menu, X, Sparkles } from "lucide-react";
import { useState } from "react";
import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { CreditsPill } from "./credits-pill";
import { SidebarNav } from "./sidebar-nav";
import { UserMenu } from "./user-menu";
import { VerifyEmailBanner } from "./verify-email-banner";

/** Signed-in creative workspace: persistent navigation, account controls and responsive drawer. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);

  const sidebar = (
    <>
      <div className="flex h-[76px] items-center border-b border-line px-5">
        <Logo href="/app" />
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-6">
        <SidebarNav onNavigate={() => setMenuOpen(false)} />
      </div>
      <div className="m-3 rounded-xl border border-line bg-surface-2/70 p-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-fg">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-brand text-white"><Sparkles className="h-3.5 w-3.5" aria-hidden /></span>
          Creative workspace
          <span className="ml-auto rounded-full bg-success-soft px-2 py-0.5 text-[10px] font-semibold text-success">LIVE</span>
        </div>
        <p className="mt-2 text-xs leading-5 text-muted">Your ideas, stories and productions in one place.</p>
      </div>
    </>
  );

  return (
    <div className="min-h-dvh bg-bg lg:grid lg:grid-cols-[240px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-dvh flex-col border-r border-line bg-surface lg:flex">
        {sidebar}
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 flex h-[76px] items-center gap-3 border-b border-line bg-bg/85 px-4 backdrop-blur-xl sm:px-7">
          <RadixDialog.Root open={menuOpen} onOpenChange={setMenuOpen}>
            <RadixDialog.Trigger className="-ml-1 inline-flex h-9 w-9 items-center justify-center rounded-lg text-fg hover:bg-surface-2 lg:hidden" aria-label="Open navigation">
              <Menu className="h-5 w-5" aria-hidden />
            </RadixDialog.Trigger>
            <RadixDialog.Portal>
              <RadixDialog.Overlay className="fixed inset-0 z-50 bg-black/60 lg:hidden" />
              <RadixDialog.Content className="fixed inset-y-0 left-0 z-50 flex w-[min(17rem,85vw)] flex-col border-r border-line bg-surface shadow-card focus:outline-none lg:hidden" aria-describedby={undefined}>
                <div className="flex h-[76px] items-center justify-between border-b border-line px-5">
                  <RadixDialog.Title className="sr-only">ASZDA navigation</RadixDialog.Title>
                  <Logo href="/app" />
                  <RadixDialog.Close className="rounded-md p-1 text-muted hover:bg-surface-2" aria-label="Close navigation">
                    <X className="h-5 w-5" aria-hidden />
                  </RadixDialog.Close>
                </div>
                <div className="flex-1 overflow-y-auto px-3 py-6"><SidebarNav onNavigate={() => setMenuOpen(false)} /></div>
              </RadixDialog.Content>
            </RadixDialog.Portal>
          </RadixDialog.Root>
          <div className="lg:hidden"><Logo href="/app" showStudio={false} /></div>
          <div className="hidden text-sm text-muted sm:block">Workspace <span className="mx-2 text-subtle">/</span><span className="font-medium text-fg">Studio</span></div>
          <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
            <CreditsPill />
            <ThemeToggle />
            <UserMenu />
          </div>
          <div aria-hidden className="brand-line pointer-events-none absolute inset-x-0 -bottom-px opacity-70" />
        </header>
        <main id="main" className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-7 sm:px-7 sm:py-9">
          <VerifyEmailBanner />
          {children}
        </main>
      </div>
    </div>
  );
}
