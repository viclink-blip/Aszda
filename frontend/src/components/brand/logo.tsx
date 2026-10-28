import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/cn";

/** The ASZDA Studio logo exactly as supplied (public/brand/aszda-logo.png, 303×317). */
export function LogoMark({ className }: { className?: string }) {
  return (
    <Image src="/brand/aszda-logo.png" alt="" width={303} height={317} priority
      className={cn("h-10 w-auto rounded-[22%]", className)} aria-hidden />
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
