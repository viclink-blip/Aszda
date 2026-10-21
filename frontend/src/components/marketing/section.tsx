import { cn } from "@/lib/cn";

export function Section({ className, children, id, bordered = true }: {
  className?: string;
  children: React.ReactNode;
  id?: string;
  bordered?: boolean;
}) {
  return (
    <section id={id} className={cn(bordered && "border-t border-line", "py-16 sm:py-24", className)}>
      <div className="container-page">{children}</div>
    </section>
  );
}

export function SectionHeading({ eyebrow, title, children, className }: {
  eyebrow?: string;
  title: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("max-w-2xl", className)}>
      {eyebrow && <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">{eyebrow}</p>}
      <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-fg sm:text-4xl">{title}</h2>
      {children && <div className="mt-4 text-base leading-relaxed text-muted sm:text-lg">{children}</div>}
    </div>
  );
}

/** Top-of-page title block for marketing and legal pages. */
export function PageHero({ eyebrow, title, children }: { eyebrow?: string; title: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="container-page pt-14 pb-10 sm:pt-20 sm:pb-14">
      {eyebrow && <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">{eyebrow}</p>}
      <h1 className="mt-3 max-w-3xl font-display text-4xl font-semibold tracking-tight text-balance text-fg sm:text-5xl">{title}</h1>
      {children && <div className="mt-5 max-w-2xl text-lg leading-relaxed text-muted">{children}</div>}
    </div>
  );
}
