"use client";

import React from "react";
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Package,
  BarChart2,
  Coins,
  Receipt,
  Percent,
} from "lucide-react";
import { formatMoney, formatPercent, parseMoney } from "@/lib/finance-utils";
import type { FinanceSummary } from "@/lib/types/finance";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/contexts/LanguageContext";

interface PremiumCardProps {
  label: string;
  value: string;
  sub?: string;
  highlight?: "positive" | "negative" | "neutral";
  icon?: React.ReactNode;
  percentage?: string;
  gradient?: string;
}

function PremiumCard({
  label,
  value,
  sub,
  highlight,
  icon,
  percentage,
  gradient,
}: PremiumCardProps) {
  return (
    <div
      className={cn(
        "group relative flex flex-col gap-2 rounded-2xl border p-5 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl",
        gradient
          ? "border-transparent bg-white/90 shadow-md shadow-zinc-100/50"
          : "border-zinc-200/80 bg-white/70 backdrop-blur-md shadow-sm shadow-zinc-100/20"
      )}
    >
      {/* Dynamic Gradient Border Accent if gradient is present */}
      {gradient && (
        <div
          className={cn(
            "absolute inset-0 -z-10 rounded-2xl p-[1.5px]",
            gradient
          )}
          style={{ content: "''" }}
        >
          <div className="h-full w-full rounded-2xl bg-white" />
        </div>
      )}

      {/* Background radial gradient accent on hover */}
      <div className="absolute inset-0 -z-10 rounded-2xl bg-gradient-to-tr from-transparent via-transparent to-zinc-50/30 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />

      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">
          {label}
        </span>
        {icon && (
          <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-zinc-100 bg-zinc-50 text-zinc-500 shadow-sm transition-all duration-300 group-hover:scale-110 group-hover:bg-zinc-100/80 group-hover:text-zinc-950">
            {icon}
          </div>
        )}
      </div>

      <div className="flex items-baseline gap-2">
        <span
          className={cn(
            "text-2xl font-bold tracking-tight transition-colors duration-300",
            highlight === "positive" && "text-emerald-600",
            highlight === "negative" && "text-rose-600",
            (!highlight || highlight === "neutral") && "text-zinc-900"
          )}
        >
          {value}
        </span>
        {percentage && (
          <span className="rounded-md bg-zinc-100/85 px-1.5 py-0.5 text-[10px] font-bold text-zinc-500">
            {percentage}
          </span>
        )}
      </div>

      {sub && (
        <span className="text-xs text-zinc-400 transition-colors duration-300 group-hover:text-zinc-500">
          {sub}
        </span>
      )}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-zinc-200/80 bg-white/70 p-5 shadow-sm">
      <div className="shimmer h-3 w-20 rounded" />
      <div className="shimmer h-7 w-32 rounded" />
      <div className="shimmer h-3.5 w-24 rounded" />
    </div>
  );
}

interface FinanceSummaryCardsProps {
  summary: FinanceSummary | null;
  isLoading: boolean;
  currency?: string;
}

export function FinanceSummaryCards({
  summary,
  isLoading,
  currency = "RUB",
}: FinanceSummaryCardsProps) {
  const { t } = useLanguage();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <div className="shimmer mb-2 h-4 w-36 rounded" />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </div>
        <div>
          <div className="shimmer mb-2 h-4 w-32 rounded" />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!summary) return null;

  const grossVal = Math.max(parseMoney(summary.grossRevenue), 1);
  const profitAfterTax = parseMoney(summary.profitAfterTax);
  const profitMargin = parseMoney(summary.profitMargin);
  const completeness = parseMoney(summary.costCompletenessPercent);

  // Helper to format a percentage of Gross Revenue
  const getPercentOfGross = (valStr: string) => {
    const val = parseMoney(valStr);
    if (val <= 0) return undefined;
    const pct = (val / grossVal) * 100;
    return `${pct.toFixed(1)}%`;
  };

  return (
    <div className="flex flex-col gap-6">
      {/* 1. Core Financial Results */}
      <div>
        <h3 className="mb-3 text-[11px] font-bold uppercase tracking-widest text-zinc-400">
          {t("financialOverview") || "Financial Overview"}
        </h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <PremiumCard
            label={t("grossRevenue")}
            value={formatMoney(summary.grossRevenue, currency)}
            icon={<DollarSign size={15} />}
            highlight="neutral"
            gradient="bg-gradient-to-tr from-indigo-500 to-purple-500"
            sub={t("grossRevenueDesc") || "Total accumulated retail sales"}
          />
          <PremiumCard
            label={t("wbForPay")}
            value={formatMoney(summary.forPay, currency)}
            icon={<Coins size={15} />}
            highlight="neutral"
            gradient="bg-gradient-to-tr from-emerald-500 to-teal-500"
            sub={t("afterWbPayout")}
          />
          <PremiumCard
            label={t("profitAfterTax")}
            value={formatMoney(summary.profitAfterTax, currency)}
            icon={profitAfterTax >= 0 ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
            highlight={profitAfterTax >= 0 ? "positive" : "negative"}
            gradient={
              profitAfterTax >= 0
                ? "bg-gradient-to-tr from-emerald-500 via-emerald-400 to-teal-400"
                : "bg-gradient-to-tr from-rose-500 to-red-500"
            }
            sub={t("netProfitDesc") || "Earnings after taxes & costs"}
          />
          <PremiumCard
            label={t("profitMarginLabel")}
            value={formatPercent(summary.profitMargin)}
            icon={<Percent size={15} />}
            highlight={profitMargin >= 0.1 ? "positive" : profitMargin < 0 ? "negative" : "neutral"}
            gradient="bg-gradient-to-tr from-violet-500 to-fuchsia-500"
            sub={t("profitMarginDesc") || "Return on retail sales"}
          />
        </div>
      </div>

      {/* 2. Deductions & Expenses */}
      <div>
        <h3 className="mb-3 text-[11px] font-bold uppercase tracking-widest text-zinc-400">
          {t("deductionsAndExpenses") || "Deductions & Expenses"}
        </h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <PremiumCard
            label={t("wbCosts")}
            value={formatMoney(summary.wbCosts, currency)}
            icon={<BarChart2 size={15} />}
            percentage={getPercentOfGross(summary.wbCosts)}
            sub={t("commissionLogistics")}
          />
          <PremiumCard
            label={t("costOfGoods")}
            value={formatMoney(summary.cogs, currency)}
            icon={<Package size={15} />}
            percentage={getPercentOfGross(summary.cogs)}
            sub={t("cogsFromSettings")}
          />
          <PremiumCard
            label={t("externalCostsLabel")}
            value={formatMoney(summary.externalAllocatedCosts, currency)}
            icon={<Coins size={15} />}
            percentage={getPercentOfGross(summary.externalAllocatedCosts)}
            sub={t("allocatedExternalSub")}
          />
          <PremiumCard
            label={t("taxAmount")}
            value={formatMoney(summary.taxAmount, currency)}
            icon={<Receipt size={15} />}
            percentage={getPercentOfGross(summary.taxAmount)}
            sub={t("taxAmountDesc") || "Calculated profit tax"}
          />
        </div>
      </div>

      {/* 3. Operational Integrity & Pre-Tax */}
      <div>
        <h3 className="mb-3 text-[11px] font-bold uppercase tracking-widest text-zinc-400">
          {t("operationalMetrics") || "Operational Efficiency"}
        </h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <PremiumCard
            label={t("profitBeforeTax")}
            value={formatMoney(summary.profitBeforeTax, currency)}
            highlight={parseMoney(summary.profitBeforeTax) >= 0 ? "positive" : "negative"}
            icon={parseMoney(summary.profitBeforeTax) >= 0 ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
            sub={t("preTaxEarnings") || "EBIT (Earnings before interest & tax)"}
          />
          <PremiumCard
            label={t("costCoverage")}
            value={formatPercent(summary.costCompletenessPercent)}
            icon={<Package size={15} />}
            highlight={completeness >= 0.9 ? "positive" : completeness < 0.5 ? "negative" : "neutral"}
            sub={`${summary.productsCount} ${t("productsCount")} / ${summary.rowsCount} ${t("rowsCount")} rows`}
          />
        </div>
      </div>
    </div>
  );
}
