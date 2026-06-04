"use client";

import React from "react";
import { formatMoney, parseMoney } from "@/lib/finance-utils";
import type { FinanceCostBreakdown } from "@/lib/types/finance";
import { useLanguage } from "@/contexts/LanguageContext";

interface FinanceCostBreakdownSectionProps {
  breakdown: FinanceCostBreakdown | null;
  isLoading: boolean;
  currency?: string;
}

export function FinanceCostBreakdownSection({
  breakdown,
  isLoading,
  currency = "RUB",
}: FinanceCostBreakdownSectionProps) {
  const { t } = useLanguage();
  if (isLoading) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-soft-sm">
        <div className="shimmer mb-4 h-4 w-32 rounded" />
        {[1, 2, 3].map((i) => (
          <div key={i} className="mb-3 flex items-center justify-between">
            <div className="shimmer h-3 w-24 rounded" />
            <div className="shimmer h-3 w-16 rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (!breakdown) return null;

  const total =
    parseMoney(breakdown.wbCosts) +
    parseMoney(breakdown.cogs) +
    parseMoney(breakdown.externalAllocatedCosts);

  const items = [
    { label: t("wbCosts"), value: breakdown.wbCosts, color: "bg-red-400" },
    { label: t("cogsFull"), value: breakdown.cogs, color: "bg-amber-400" },
    { label: t("externalAllocatedLabel"), value: breakdown.externalAllocatedCosts, color: "bg-purple-400" },
  ];

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-soft-sm">
      <h3 className="mb-4 text-sm font-semibold text-zinc-950">{t("costBreakdownTitle")}</h3>

      <div className="space-y-3">
        {items.map(({ label, value, color }) => {
          const num = parseMoney(value);
          const pct = total > 0 ? (num / total) * 100 : 0;
          return (
            <div key={label}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="text-zinc-600">{label}</span>
                <span className="font-medium text-zinc-900">
                  {formatMoney(value, currency)}
                  <span className="ml-1.5 text-xs text-zinc-400">
                    {pct.toFixed(0)}%
                  </span>
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-100">
                <div
                  className={`h-full rounded-full ${color} transition-all duration-500`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}

        <div className="border-t border-zinc-100 pt-3">
          <div className="flex items-center justify-between text-sm font-semibold">
            <span className="text-zinc-700">{t("totalCosts")}</span>
            <span className="text-zinc-950">{formatMoney(total, currency)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
