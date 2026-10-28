import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

/*
 * Hero illustration: the production pipeline as a "call sheet".
 * It is a diagram of the workflow, not a screenshot, and it marks which steps
 * exist today and which are planned.
 */

const STEPS: { n: string; title: string; detail: string; status: "ready" | "planned" }[] = [
  { n: "01", title: "Idea", detail: "Your story, ad or concept", status: "ready" },
  { n: "02", title: "Script", detail: "Concept, script, scene breakdown · Claude", status: "ready" },
  { n: "03", title: "Characters & storyboard", detail: "Project workspace", status: "ready" },
  { n: "04", title: "Video & animation", detail: "Text or image to video · Runway", status: "ready" },
  { n: "05", title: "Voice", detail: "Narration and dialogue · OpenAI", status: "ready" },
  { n: "06", title: "Your finished film", detail: "Scenes and voices joined into one video", status: "ready" },
];

export function WorkflowBoard() {
  return (
    <div className="relative rounded-2xl border border-line bg-surface p-2 shadow-card">
      <div className="flex items-center justify-between rounded-t-xl border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-accent" aria-hidden />
          <span className="font-mono text-xs tracking-wide text-muted uppercase">Production pipeline</span>
        </div>
        <span className="font-mono text-xs text-subtle">ASZDA Studio</span>
      </div>
      <ol className="divide-y divide-line">
        {STEPS.map((step) => (
          <li key={step.n} className="flex items-center gap-4 px-4 py-3.5">
            <span className="font-mono text-xs text-subtle tabular-nums">{step.n}</span>
            <div className="min-w-0 flex-1">
              <p className={cn("text-sm font-medium", step.status === "planned" ? "text-muted" : "text-fg")}>{step.title}</p>
              <p className="truncate text-xs text-subtle">{step.detail}</p>
            </div>
            {step.status === "planned" ? (
              <Badge tone="warning">Planned</Badge>
            ) : (
              <ArrowRight className="h-4 w-4 text-subtle" aria-hidden />
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
