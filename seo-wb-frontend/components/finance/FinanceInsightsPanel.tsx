"use client";

import React from "react";
import { AlertTriangle, Info, XCircle, ChevronRight } from "lucide-react";
import type { FinanceInsight } from "@/lib/types/finance";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { useLanguage } from "@/contexts/LanguageContext";

interface FinanceInsightsPanelProps {
  insights: FinanceInsight[];
  isLoading: boolean;
}

function InsightCard({ insight }: { insight: FinanceInsight }) {
  const { t } = useLanguage();
  const levelStyles = {
    info: {
      border: "border-blue-200",
      bg: "bg-blue-50",
      icon: <Info size={15} className="text-blue-500" />,
      title: "text-blue-800",
      body: "text-blue-700",
    },
    warning: {
      border: "border-amber-200",
      bg: "bg-amber-50",
      icon: <AlertTriangle size={15} className="text-amber-500" />,
      title: "text-amber-800",
      body: "text-amber-700",
    },
    danger: {
      border: "border-red-200",
      bg: "bg-red-50",
      icon: <XCircle size={15} className="text-red-500" />,
      title: "text-red-800",
      body: "text-red-700",
    },
  };

  const styles = levelStyles[insight.level] ?? levelStyles.info;

  const linkMap: Record<string, string> = {
    missing_cost_settings: "/finance/product-settings",
    unmapped_rows: "/finance/product-settings",
    negative_profit: "/finance",
    high_logistics: "/finance",
    high_return_rate: "/finance",
  };

  const linkHref = linkMap[insight.type];

  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-lg border p-3",
        styles.border,
        styles.bg
      )}
    >
      <span className="mt-0.5 shrink-0">{styles.icon}</span>
      <div className="min-w-0 flex-1">
        <p className={cn("text-sm font-medium", styles.title)}>{insight.message}</p>
        {insight.recommendedAction && (
          <p className={cn("mt-0.5 text-xs", styles.body)}>{insight.recommendedAction}</p>
        )}
        {insight.productIds?.length > 0 && (
          <p className="mt-1 text-xs text-zinc-500">
            {t("affectedProducts")} {insight.productIds.length}
          </p>
        )}
      </div>
      {linkHref && (
        <Link
          href={linkHref}
          className={cn("shrink-0 rounded p-1 transition-colors hover:bg-white/50", styles.body)}
        >
          <ChevronRight size={14} />
        </Link>
      )}
    </div>
  );
}

export function FinanceInsightsPanel({
  insights,
  isLoading,
}: FinanceInsightsPanelProps) {
  const { t } = useLanguage();
  if (isLoading) {
    return (
      <div className="space-y-2">
        {[1, 2].map((i) => (
          <div key={i} className="shimmer h-16 rounded-lg" />
        ))}
      </div>
    );
  }

  if (!insights.length) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
        <Info size={15} className="text-green-500" />
        <p className="text-sm text-green-700">{t("noIssuesDetected")}</p>
      </div>
    );
  }

  const sorted = [...insights].sort((a, b) => {
    const order = { danger: 0, warning: 1, info: 2 };
    return (order[a.level] ?? 3) - (order[b.level] ?? 3);
  });

  return (
    <div className="space-y-2">
      {sorted.map((insight, i) => (
        <InsightCard key={i} insight={insight} />
      ))}
    </div>
  );
}
