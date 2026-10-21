"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { ButtonLink } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";

export const MARKETING_NAV = [
  { href: "/features", label: "Features" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/pricing", label: "Pricing" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const { status } = useAuth();
  const [open, setOpen] = useState(false);
  const signedIn = status === "authenticated";

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-bg/85 backdrop-blur-md">
      <div className="container-page flex h-16 items-center justify-between gap-4">
        <Logo />
        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {MARKETING_NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={pathname === item.href ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-2 text-sm text-muted hover:text-fg",
                pathname === item.href && "text-fg",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-1.5">
          <ThemeToggle />
          {signedIn ? (
            <ButtonLink href="/app" size="sm" className="hidden sm:inline-flex">Open studio</ButtonLink>
          ) : (
            <>
              <Link href="/sign-in" className="hidden rounded-md px-3 py-2 text-sm font-medium text-fg hover:bg-surface-2 sm:inline-block">
                Sign in
              </Link>
              <ButtonLink href="/sign-up" size="sm" className="hidden sm:inline-flex">Start creating</ButtonLink>
            </>
          )}
          <RadixDialog.Root open={open} onOpenChange={setOpen}>
            <RadixDialog.Trigger className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-fg hover:bg-surface-2 md:hidden" aria-label="Open menu">
              <Menu className="h-5 w-5" aria-hidden />
            </RadixDialog.Trigger>
            <RadixDialog.Portal>
              <RadixDialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
              <RadixDialog.Content className="fixed inset-y-0 right-0 z-50 flex w-[min(20rem,100vw)] flex-col bg-surface p-5 shadow-card focus:outline-none" aria-describedby={undefined}>
                <div className="flex items-center justify-between">
                  <RadixDialog.Title className="font-display font-semibold">Menu</RadixDialog.Title>
                  <RadixDialog.Close className="rounded-md p-1 text-muted hover:bg-surface-2" aria-label="Close menu">
                    <X className="h-5 w-5" aria-hidden />
                  </RadixDialog.Close>
                </div>
                <nav aria-label="Mobile" className="mt-6 flex flex-col gap-1">
                  {MARKETING_NAV.map((item) => (
                    <Link key={item.href} href={item.href} onClick={() => setOpen(false)} className="rounded-md px-3 py-2.5 text-fg hover:bg-surface-2">
                      {item.label}
                    </Link>
                  ))}
                </nav>
                <div className="mt-auto flex flex-col gap-2 border-t border-line pt-4">
                  {signedIn ? (
                    <ButtonLink href="/app" onClick={() => setOpen(false)}>Open studio</ButtonLink>
                  ) : (
                    <>
                      <ButtonLink href="/sign-up" onClick={() => setOpen(false)}>Start creating</ButtonLink>
                      <ButtonLink href="/sign-in" variant="outline" onClick={() => setOpen(false)}>Sign in</ButtonLink>
                    </>
                  )}
                </div>
              </RadixDialog.Content>
            </RadixDialog.Portal>
          </RadixDialog.Root>
        </div>
      </div>
    </header>
  );
}
