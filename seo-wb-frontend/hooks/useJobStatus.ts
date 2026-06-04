"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export interface CardJobStatus {
  id: number;
  status: "queued" | "running" | "completed" | "failed" | string;
  step: string;
  error?: string | null;
  result?: unknown;
}

export function useJobStatus(jobId: number | null) {
  const [job, setJob] = useState<CardJobStatus | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  useEffect(() => {
    if (!jobId) {
      queueMicrotask(() => {
        setJob(null);
        setIsPolling(false);
      });
      return;
    }

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      if (cancelled) return;
      setIsPolling(true);
      try {
        const nextJob = await api.get(`/cards/jobs/${jobId}`);
        if (cancelled) return;
        setJob(nextJob);
        if (nextJob?.status === "completed" || nextJob?.status === "failed") {
          setIsPolling(false);
          return;
        }
      } catch {
        if (!cancelled) setIsPolling(false);
        return;
      }
      timeoutId = setTimeout(poll, 2500);
    };

    poll();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [jobId]);

  return { job, isPolling };
}
