import { ArrowRight } from "lucide-react";
import { ButtonLink } from "@/components/ui/button";

export function CtaBand() {
  return (
    <section className="border-t border-line">
      <div className="container-page py-16 sm:py-20">
        <div className="flex flex-col items-start justify-between gap-6 rounded-2xl bg-fg px-6 py-10 text-bg sm:flex-row sm:items-center sm:px-10">
          <div>
            <h2 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">Imagine It. Create It.</h2>
            <p className="mt-2 max-w-lg text-bg/70">
              Create an account, start a project and plan your first story today.
            </p>
          </div>
          <ButtonLink href="/sign-up" size="lg">
            Start creating <ArrowRight className="h-4 w-4" aria-hidden />
          </ButtonLink>
        </div>
      </div>
    </section>
  );
}
