import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import { cn } from "@/lib/cn";

type NoticeTone = "info" | "success" | "warning" | "danger";

const STYLES: Record<NoticeTone, { box: string; Icon: typeof Info }> = {
  info: { box: "border-info/25 bg-info-soft text-info", Icon: Info },
  success: { box: "border-success/25 bg-success-soft text-success", Icon: CheckCircle2 },
  warning: { box: "border-warning/25 bg-warning-soft text-warning", Icon: AlertTriangle },
  danger: { box: "border-danger/25 bg-danger-soft text-danger", Icon: XCircle },
};

/** A coloured message box: explanations, warnings, honest "not available" notes. */
export function Notice({ tone = "info", title, children, action, className }: {
  tone?: NoticeTone;
  title?: React.ReactNode;
  children?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  const { box, Icon } = STYLES[tone];
  return (
    <div className={cn("flex flex-col gap-3 rounded-lg border px-4 py-3 sm:flex-row sm:items-start", box, className)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1 text-sm">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn("text-fg/80", Boolean(title) && "mt-0.5")}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
