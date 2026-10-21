import Link from "next/link";
import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/components/theme/theme-toggle";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="container-page flex h-16 items-center justify-between">
        <Logo />
        <ThemeToggle />
      </header>
      <main id="main" className="flex flex-1 items-start justify-center px-4 py-8 sm:items-center sm:py-12">
        {children}
      </main>
      <footer className="container-page flex flex-wrap justify-center gap-4 py-6 text-xs text-subtle">
        <Link href="/privacy" className="hover:text-fg">Privacy</Link>
        <Link href="/terms" className="hover:text-fg">Terms</Link>
        <Link href="/contact" className="hover:text-fg">Contact</Link>
      </footer>
    </div>
  );
}
