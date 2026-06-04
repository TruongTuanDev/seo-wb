"use client";

import React, { useState } from "react";
import { Search, AlertTriangle } from "lucide-react";
import { formatMoney, formatPercent, formatQuantity, isProfitNegative, parseMoney } from "@/lib/finance-utils";
import type { FinanceProductBreakdownItem } from "@/lib/types/finance";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/contexts/LanguageContext";

interface ProductBreakdownTableProps {
  items: FinanceProductBreakdownItem[];
  total: number;
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  currency?: string;
}

export function ProductBreakdownTable({
  items,
  total,
  isLoading,
  isLoadingMore,
  hasMore,
  currency = "RUB",
}: ProductBreakdownTableProps) {
  const { t } = useLanguage();
  const [search, setSearch] = useState("");

  const filtered = search.trim()
    ? items.filter(
        (it) =>
          it.title?.toLowerCase().includes(search.toLowerCase()) ||
          it.vendorCode?.toLowerCase().includes(search.toLowerCase()) ||
          String(it.nmId ?? "").includes(search)
      )
    : items;

  if (isLoading) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white shadow-soft-sm overflow-hidden">
        <div className="p-4">
          <div className="shimmer h-9 w-full max-w-xs rounded-md" />
        </div>
        <div className="divide-y divide-zinc-100">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex gap-4 px-4 py-3">
              <div className="shimmer h-4 w-16 rounded" />
              <div className="shimmer h-4 w-32 rounded" />
              <div className="shimmer h-4 w-20 rounded" />
              <div className="shimmer h-4 w-20 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-zinc-200 bg-white py-14 text-center">
        <Search size={28} className="text-zinc-300" />
        <p className="text-sm font-medium text-zinc-500">{t("noProductData")}</p>
        <p className="text-xs text-zinc-400">{t("runFinanceSync")}</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-200 bg-white shadow-soft-sm overflow-hidden">
      <div className="flex items-center gap-3 border-b border-zinc-100 p-3">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            placeholder={t("searchProduct")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-zinc-300 bg-white py-2 pl-8 pr-3 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-indigo-100"
          />
        </div>
        <span className="text-xs text-zinc-400">{total} {t("productsTotalCount")}</span>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-100 bg-zinc-50">
              {[
                t("colNmId"),
                t("colTitle"),
                t("colQty"),
                t("grossRevenue"),
                t("colForPay"),
                t("wbCosts"),
                t("colCogs"),
                t("colTax"),
                t("colProfitAfterTax"),
                t("colMargin"),
                t("colStatus"),
              ].map((col) => (
                <th
                  key={col}
                  className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-zinc-400"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-50">
            {filtered.map((item, idx) => {
              const negative = isProfitNegative(item.profitAfterTax);
              const missingCost = !item.hasCostSettings;
              const margin = parseMoney(item.profitMargin);
              const highReturn = margin < -0.05;

              return (
                <tr
                  key={item.productId ?? idx}
                  className={cn(
                    "transition-colors hover:bg-zinc-50/50",
                    negative && "bg-red-50/40 hover:bg-red-50/60"
                  )}
                >
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <div className="text-xs font-medium text-zinc-700">
                      {item.nmId ?? "—"}
                    </div>
                    <div className="text-xs text-zinc-400">{item.vendorCode ?? "—"}</div>
                  </td>
                  <td className="max-w-[180px] px-3 py-2.5">
                    <span className="block truncate text-zinc-800" title={item.title ?? ""}>
                      {item.title ?? <span className="text-zinc-400">{t("unmappedProduct")}</span>}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-zinc-700">
                    {formatQuantity(item.quantity)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-zinc-700">
                    {formatMoney(item.grossRevenue, currency)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-zinc-700">
                    {formatMoney(item.forPay, currency)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-zinc-700">
                    {formatMoney(item.wbCosts, currency)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-zinc-700">
                    {formatMoney(item.cogs, currency)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-zinc-700">
                    {formatMoney(item.taxAmount, currency)}
                  </td>
                  <td
                    className={cn(
                      "whitespace-nowrap px-3 py-2.5 font-medium",
                      negative ? "text-red-600" : "text-green-600"
                    )}
                  >
                    {formatMoney(item.profitAfterTax, currency)}
                  </td>
                  <td
                    className={cn(
                      "whitespace-nowrap px-3 py-2.5",
                      negative || highReturn ? "text-red-600" : "text-zinc-700"
                    )}
                  >
                    {formatPercent(item.profitMargin)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {negative && (
                        <span className="inline-flex items-center gap-0.5 rounded-full bg-red-100 px-1.5 py-0.5 text-xs text-red-600">
                          <AlertTriangle size={10} /> {t("statusLoss")}
                        </span>
                      )}
                      {missingCost && (
                        <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-xs text-amber-700">
                          <AlertTriangle size={10} /> {t("statusNoCost")}
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="border-t border-zinc-100 px-4 py-3 text-center text-xs text-zinc-400">
        {isLoadingMore ? "Loading more products..." : hasMore ? "Scroll to load more" : total > 0 ? "End of list" : ""}
      </div>
    </div>
  );
}
