"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { Menu, X } from "lucide-react";
import { useState } from "react";
import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { SidebarNav } from "./sidebar-nav";
import { UserMenu } from "./user-menu";
import { VerifyEmailBanner } from "./verify-email-banner";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);

  const sidebar = (
    <>
      <div className="flex h-12 items-center px-2">
        <Logo href="/app" />
      </div>
      <div className="flex-1 overflow-y-auto py-1">
        <SidebarNav onNavigate={() => setMenuOpen(false)} />
      </div>
      <div className="mt-auto rounded-[13px] border border-[#292d3d] bg-[#12141e] p-3.5">
        <div className="flex items-center justify-between gap-2 text-xs font-semibold text-[#f4f5fb]">
          <span>Creative workspace</span>
          <span className="rounded-full bg-[#15372e] px-2 py-0.5 text-[10px] font-semibold text-[#80e3b9]">DEMO</span>
        </div>
        <p className="mt-1 text-xs leading-5 text-[#9ba1b5]">Your ideas, stories and productions in one place.</p>
      </div>
    </>
  );

  return (
    <div className="min-h-dvh bg-[#090a10] text-[#f4f5fb] lg:grid lg:grid-cols-[240px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-dvh flex-col gap-7 border-r border-[#292d3d] bg-[#0d0e16] px-4 py-6 lg:flex">
        {sidebar}
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 flex h-[72px] items-center gap-3 border-b border-[#292d3d] bg-[#0b0c14]/90 px-4 backdrop-blur-xl sm:px-[34px]">
          <RadixDialog.Root open={menuOpen} onOpenChange={setMenuOpen}>
            <RadixDialog.Trigger className="-ml-1 inline-flex h-9 w-9 items-center justify-center rounded-lg text-[#f4f5fb] hover:bg-[#191c29] lg:hidden" aria-label="Open navigation">
              <Menu className="h-5 w-5" aria-hidden />
            </RadixDialog.Trigger>
            <RadixDialog.Portal>
              <RadixDialog.Overlay className="fixed inset-0 z-50 bg-black/60 lg:hidden" />
              <RadixDialog.Content className="fixed inset-y-0 left-0 z-50 flex w-[min(17rem,85vw)] flex-col gap-7 border-r border-[#292d3d] bg-[#0d0e16] px-4 py-6 shadow-2xl focus:outline-none lg:hidden" aria-describedby={undefined}>
                <div className="flex h-12 items-center justify-between px-2">
                  <RadixDialog.Title className="sr-only">ASZDA navigation</RadixDialog.Title>
                  <Logo href="/app" />
                  <RadixDialog.Close className="rounded-md p-1 text-[#9ba1b5] hover:bg-[#191c29]" aria-label="Close navigation">
                    <X className="h-5 w-5" aria-hidden />
                  </RadixDialog.Close>
                </div>
                <div className="flex-1 overflow-y-auto"><SidebarNav onNavigate={() => setMenuOpen(false)} /></div>
              </RadixDialog.Content>
            </RadixDialog.Portal>
          </RadixDialog.Root>
          <div className="hidden text-sm text-[#9ba1b5] sm:block">
            Workspace <span className="mx-2 text-[#626981]">/</span><span className="font-semibold text-white">Dashboard</span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden text-xs text-[#9ba1b5] sm:inline">✧ Demo workspace</span>
            <ThemeToggle />
            <UserMenu />
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-[1180px] flex-1 px-4 py-[22px] sm:px-[34px] sm:py-[34px]">
          <VerifyEmailBanner />
          {children}
        </main>
      </div>
    </div>
  );
}
