"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

export type DraftAutosaveStatus = "idle" | "saving" | "saved" | "error";

export function useDraftAutosave({
  draftId,
  payload,
  enabled,
  delay = 1200,
}: {
  draftId: number | null;
  payload: unknown | null;
  enabled: boolean;
  delay?: number;
}) {
  const [status, setStatus] = useState<DraftAutosaveStatus>("idle");
  const lastSavedRef = useRef("");
  const hydratedRef = useRef(false);
  const signature = payload ? JSON.stringify(payload) : "";

  useEffect(() => {
    if (!draftId || !enabled || !payload || !signature) return;
    if (!hydratedRef.current) {
      hydratedRef.current = true;
      lastSavedRef.current = signature;
      return;
    }
    if (lastSavedRef.current === signature) return;

    const timeoutId = setTimeout(async () => {
      setStatus("saving");
      try {
        await api.put(`/cards/drafts/${draftId}`, { card_payload: payload });
        lastSavedRef.current = signature;
        setStatus("saved");
      } catch {
        setStatus("error");
      }
    }, delay);

    return () => clearTimeout(timeoutId);
  }, [draftId, enabled, payload, signature, delay]);

  return status;
}
