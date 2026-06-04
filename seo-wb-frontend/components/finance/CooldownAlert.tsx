"use client";

import React from "react";
import { AlertTriangle, Clock } from "lucide-react";
import { formatRetryAfter } from "@/lib/finance-utils";
import type { CooldownInfo } from "@/lib/types/finance";
import { useLanguage } from "@/contexts/LanguageContext";

interface CooldownAlertProps {
  cooldowns: CooldownInfo[];
  category?: string;
}

export function CooldownAlert({ cooldowns, category }: CooldownAlertProps) {
  const { t } = useLanguage();
  const filtered = category
    ? cooldowns.filter((c) => c.category === category)
    : cooldowns;

  if (!filtered.length) return null;

  const maxRetry = Math.max(...filtered.map((c) => c.retryAfterSeconds ?? 0));

  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-600" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-amber-800">
          {t("cooldownActive")}
          {category && ` (${category})`}
        </p>
        <p className="mt-0.5 text-xs text-amber-700">
          {t("cooldownDesc")}{" "}
          <span className="inline-flex items-center gap-1 font-semibold">
            <Clock size={11} />
            {formatRetryAfter(maxRetry)}
          </span>
          . {t("cooldownExpiry")}
        </p>
        {filtered.map((c, i) => (
          <p key={i} className="mt-1 truncate text-xs text-amber-600">
            {c.endpoint} — {formatRetryAfter(c.retryAfterSeconds)}
          </p>
        ))}
      </div>
    </div>
  );
}
