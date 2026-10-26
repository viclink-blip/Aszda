"use client";

import { Send } from "lucide-react";
import { useRef, useState } from "react";
import { useCredits } from "@/components/app/credits-context";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/ui/field";
import { Textarea } from "@/components/ui/input";
import { api, ApiError, errorMessage, newIdempotencyKey } from "@/lib/api";
import type { Job } from "@/lib/types";

/**
 * Reply to a finished text answer. Only the reference to this answer is sent; the server
 * rebuilds the earlier conversation itself and reserves credits for it like any job.
 */
export function ContinueConversation({ job, onStarted }: { job: Job; onStarted: (job: Job) => void }) {
  const { refresh } = useCredits();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Reused if sending fails on the network, so a retry cannot start (and charge) twice.
  const key = useRef<string | null>(null);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;
    setBusy(true);
    setError(null);
    key.current ??= newIdempotencyKey();
    try {
      const { job: created } = await api.generation.create({
        provider: job.provider, model: job.model, kind: "text", project_id: job.project_id,
        params: {
          task: job.params.task ?? "freeform", prompt: message.trim(),
          max_output_tokens: job.params.max_output_tokens ?? 4000, effort: job.params.effort ?? "medium",
          continue_from_job_id: job.id,
        },
      }, key.current);
      key.current = null;
      setMessage("");
      void refresh();
      onStarted(created);
    } catch (err) {
      if (!(err instanceof ApiError && err.isNetworkError)) key.current = null;
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={send} className="mt-4 flex flex-col gap-2 border-t border-line pt-4">
      <label htmlFor={`reply-${job.id}`} className="text-sm font-medium text-fg">Continue the conversation</label>
      <Textarea id={`reply-${job.id}`} rows={3} maxLength={12000} value={message} placeholder="For example: Yes, write the pilot scene."
        onChange={(e) => setMessage(e.target.value)} />
      <p className="text-xs text-subtle">Claude sees the earlier messages. A reply costs credits like any generation, a little more as the conversation grows.</p>
      <FormError message={error} />
      <div><Button type="submit" size="sm" loading={busy} disabled={!message.trim()}><Send className="h-4 w-4" aria-hidden /> Send</Button></div>
    </form>
  );
}
