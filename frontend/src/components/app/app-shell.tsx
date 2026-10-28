"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { Menu, X } from "lucide-react";
import { useState } from "react";
import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { CreditsPill } from "./credits-pill";
import { SidebarNav } from "./sidebar-nav";
import { UserMenu } from "./user-menu";
import { VerifyEmailBanner } from "./verify-email-banner";

/** Signed-in layout: sidebar on desktop, drawer on mobile, header with credits and account. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[15.5rem_1fr]">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh flex-col border-r border-line bg-surface lg:flex">
        <div className="flex h-16 items-center px-5">
          <Logo href="/app" />
        </div>
        <div className="flex-1 overflow-y-auto px-3 pt-2 pb-6">
          <SidebarNav />
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-2 border-b border-line bg-bg/85 px-4 backdrop-blur-md sm:px-6">
          {/* Mobile drawer */}
          <RadixDialog.Root open={menuOpen} onOpenChange={setMenuOpen}>
            <RadixDialog.Trigger className="-ml-1 inline-flex h-9 w-9 items-center justify-center rounded-lg text-fg hover:bg-surface-2 lg:hidden" aria-label="Open navigation">
              <Menu className="h-5 w-5" aria-hidden />
            </RadixDialog.Trigger>
            <RadixDialog.Portal>
              <RadixDialog.Overlay className="fixed inset-0 z-50 bg-black/40 lg:hidden" />
              <RadixDialog.Content className="fixed inset-y-0 left-0 z-50 flex w-[min(17rem,85vw)] flex-col bg-surface shadow-card focus:outline-none lg:hidden" aria-describedby={undefined}>
                <div className="flex h-16 items-center justify-between px-5">
                  <RadixDialog.Title className="sr-only">Navigation</RadixDialog.Title>
                  <Logo href="/app" />
                  <RadixDialog.Close className="rounded-md p-1 text-muted hover:bg-surface-2" aria-label="Close navigation">
                    <X className="h-5 w-5" aria-hidden />
                  </RadixDialog.Close>
                </div>
                <div className="flex-1 overflow-y-auto px-3 pb-6">
                  <SidebarNav onNavigate={() => setMenuOpen(false)} />
                </div>
              </RadixDialog.Content>
            </RadixDialog.Portal>
          </RadixDialog.Root>
          <div className="lg:hidden">
            <Logo href="/app" showStudio={false} />
          </div>
          <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
            <CreditsPill />
            <ThemeToggle />
            <UserMenu />
          </div>
          {/* Thin neon line in the logo's colours. */}
          <div aria-hidden className="brand-line pointer-events-none absolute inset-x-0 -bottom-px opacity-60" />
        </header>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
          <VerifyEmailBanner />
          {children}
        </main>
      </div>
    </div>
  );
}
