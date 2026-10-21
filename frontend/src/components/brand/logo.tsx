import Link from "next/link";
import { cn } from "@/lib/cn";

/** The ASZDA mark: a frame with a rising "A" — a lens/aperture read as a letter. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("h-8 w-8", className)} aria-hidden focusable="false">
      <rect x="1" y="1" width="30" height="30" rx="8" className="fill-fg" />
      <path d="M16 7.5 24.5 24h-4.1L16 15.2 11.6 24H7.5L16 7.5Z" className="fill-bg" />
      <rect x="13.2" y="19.6" width="5.6" height="2.6" rx="1" className="fill-accent" />
    </svg>
  );
}

export function Logo({ href = "/", className, showStudio = true }: { href?: string; className?: string; showStudio?: boolean }) {
  return (
    <Link href={href} className={cn("inline-flex items-center gap-2.5 rounded-md", className)} aria-label="ASZDA Studio home">
      <LogoMark />
      <span className="font-display text-[17px] leading-none font-semibold tracking-tight text-fg">
        ASZDA{showStudio && <span className="font-normal text-muted"> Studio</span>}
      </span>
    </Link>
  );
}
