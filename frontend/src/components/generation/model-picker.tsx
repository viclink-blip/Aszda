"use client";

import { CircleSlash } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";
import { unavailableText } from "@/lib/format";
import type { ModelOption } from "@/hooks/use-providers";

/**
 * Choose a model. Unavailable models are listed (so people know they exist)
 * but disabled, with the reason in plain words.
 */
export function ModelPicker({ options, value, onChange }: {
  options: ModelOption[];
  value: string | null;
  onChange: (key: string) => void;
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium text-fg">Model</legend>
      <div role="radiogroup" aria-label="Model" className="flex flex-col gap-2">
        {options.map(({ key, provider, model }) => {
          const selected = value === key;
          const available = model.available;
          const reasonId = `${key}-reason`;
          return (
            <button
              key={key}
              type="button"
              role="radio"
              aria-checked={selected && available}
              aria-disabled={!available}
              aria-describedby={available ? undefined : reasonId}
              disabled={!available}
              onClick={() => available && onChange(key)}
              className={cn(
                "flex w-full flex-col gap-1 rounded-lg border p-3 text-left transition-colors",
                selected && available ? "border-accent bg-accent-soft/40" : "border-line",
                available ? "hover:border-line-strong" : "cursor-not-allowed bg-surface-2/60",
              )}
            >
              <span className="flex flex-wrap items-center gap-2">
                <span className={cn("text-sm font-medium", available ? "text-fg" : "text-muted")}>{model.label}</span>
                <span className="text-xs text-subtle">{provider.label}</span>
                {available ? (
                  selected && <Badge tone="accent">Selected</Badge>
                ) : (
                  <Badge tone="neutral"><CircleSlash className="h-3 w-3" aria-hidden /> Unavailable</Badge>
                )}
              </span>
              <span className="text-xs text-muted">{model.description}</span>
              {model.deprecated && (
                <span className="text-xs text-warning">{model.deprecated}</span>
              )}
              {!available && (
                <span id={reasonId} className="text-xs text-warning">{unavailableText(model.unavailable_reason)}</span>
              )}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
