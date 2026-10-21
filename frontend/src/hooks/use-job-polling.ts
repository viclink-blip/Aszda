"use client";

import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { isJobActive, type Job } from "@/lib/types";

const POLL_MS = 3000;

/**
 * Keep one generation job up to date.
 * While the job is queued/validating/processing we fetch it every ~3 seconds;
 * polling stops by itself once it is completed, failed or cancelled.
 * Call setJob(newJob) after submitting to start following a new job.
 */
export function useJobPolling(initialJob: Job | null = null) {
  const [job, setJob] = useState<Job | null>(initialJob);
  const [pollError, setPollError] = useState<string | null>(null);

  const jobId = job?.id;
  const active = job ? isJobActive(job.status) : false;

  useEffect(() => {
    if (!jobId || !active) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;

    const tick = async () => {
      try {
        const { job: fresh } = await api.generation.get(jobId);
        if (stopped) return;
        setJob(fresh);
        setPollError(null);
      } catch (error) {
        if (!stopped) setPollError(errorMessage(error));
      }
      // When the job becomes final, `active` flips and this effect is cleaned up.
      if (!stopped) timer = setTimeout(tick, POLL_MS);
    };

    timer = setTimeout(tick, POLL_MS);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [jobId, active]);

  return { job, setJob, pollError };
}

/**
 * Call `callback` every few seconds while `enabled` is true.
 * Used by job lists to refresh while any job in them is still running.
 */
export function usePolling(callback: () => unknown, enabled: boolean, intervalMs = POLL_MS) {
  const callbackRef = useRef(callback);
  useEffect(() => {
    callbackRef.current = callback;
  });

  useEffect(() => {
    if (!enabled) return;
    const timer = setInterval(() => void callbackRef.current(), intervalMs);
    return () => clearInterval(timer);
  }, [enabled, intervalMs]);
}
