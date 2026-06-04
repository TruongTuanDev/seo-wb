"use client";

import React, { useMemo, useState, useCallback } from "react";
import { formatMoney, parseMoney, formatDate } from "@/lib/finance-utils";
import type { FinanceTimelinePoint } from "@/lib/types/finance";
import { Eye, EyeOff, Activity } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/contexts/LanguageContext";

interface FinanceTimelineChartProps {
  items: FinanceTimelinePoint[];
  isLoading: boolean;
  currency?: string;
}

const CHART_WIDTH = 800;
const CHART_HEIGHT = 280;
const PADDING = { top: 20, right: 20, bottom: 40, left: 65 };

function formatCompactMoney(value: number, currency = "RUB"): string {
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency,
      notation: "compact",
      compactDisplay: "short",
      minimumFractionDigits: 0,
      maximumFractionDigits: 1,
    }).format(value);
  } catch {
    return String(Math.round(value));
  }
}

export function FinanceTimelineChart({
  items,
  isLoading,
  currency = "RUB",
}: FinanceTimelineChartProps) {
  const { t } = useLanguage();

  // Series visibility state
  const [showRevenue, setShowRevenue] = useState(true);
  const [showPayout, setShowPayout] = useState(true);
  const [showProfit, setShowProfit] = useState(true);

  // Active hover bucket index
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  // Parse items into numeric lists
  const chartData = useMemo(() => {
    return items.map((item) => ({
      bucket: item.bucket,
      revenue: parseMoney(item.grossRevenue),
      payout: parseMoney(item.forPay),
      profit: parseMoney(item.profitAfterTax),
    }));
  }, [items]);

  // Calculate Y-axis scaling boundaries dynamically based on active series
  const bounds = useMemo(() => {
    if (!chartData.length) return { min: 0, max: 100 };

    const vals: number[] = [];
    chartData.forEach((d) => {
      if (showRevenue) vals.push(d.revenue);
      if (showPayout) vals.push(d.payout);
      if (showProfit) vals.push(d.profit);
    });

    if (vals.length === 0) return { min: 0, max: 100 };

    let maxVal = Math.max(...vals);
    let minVal = Math.min(...vals);

    // Padding values slightly for aesthetic buffer
    if (maxVal === minVal) {
      maxVal += 100;
      minVal -= 100;
    } else {
      const buffer = (maxVal - minVal) * 0.1;
      maxVal += buffer;
      minVal = Math.min(minVal - buffer, 0); // clamp minimum at 0 unless negative values exist
    }

    return { min: minVal, max: maxVal };
  }, [chartData, showRevenue, showPayout, showProfit]);

  const yRange = bounds.max - bounds.min;

  // Coordinate getters
  const getX = useCallback((index: number) => {
    if (chartData.length <= 1) return PADDING.left;
    return (
      PADDING.left +
      (index / (chartData.length - 1)) *
        (CHART_WIDTH - PADDING.left - PADDING.right)
    );
  }, [chartData.length]);

  const getY = useCallback((val: number) => {
    return (
      PADDING.top +
      ((bounds.max - val) / yRange) *
        (CHART_HEIGHT - PADDING.top - PADDING.bottom)
    );
  }, [bounds.max, yRange]);

  // Zero-line coordinate (if range spans negative values)
  const yZero = useMemo(() => {
    if (bounds.min < 0 && bounds.max > 0) {
      return getY(0);
    }
    return getY(bounds.min); // default to bottom of chart
  }, [bounds, getY]);

  // Generate SVG path strings
  const paths = useMemo(() => {
    if (chartData.length < 2) return { revenue: "", payout: "", profit: "", revArea: "", payArea: "", profArea: "" };

    let revLine = "";
    let payLine = "";
    let profLine = "";
    let revArea = "";
    let payArea = "";
    let profArea = "";

    chartData.forEach((d, i) => {
      const x = getX(i);
      const yRev = getY(d.revenue);
      const yPay = getY(d.payout);
      const yProf = getY(d.profit);

      if (i === 0) {
        revLine = `M ${x} ${yRev}`;
        payLine = `M ${x} ${yPay}`;
        profLine = `M ${x} ${yProf}`;
        revArea = `M ${x} ${yZero} L ${x} ${yRev}`;
        payArea = `M ${x} ${yZero} L ${x} ${yPay}`;
        profArea = `M ${x} ${yZero} L ${x} ${yProf}`;
      } else {
        revLine += ` L ${x} ${yRev}`;
        payLine += ` L ${x} ${yPay}`;
        profLine += ` L ${x} ${yProf}`;
        revArea += ` L ${x} ${yRev}`;
        payArea += ` L ${x} ${yPay}`;
        profArea += ` L ${x} ${yProf}`;
      }

      if (i === chartData.length - 1) {
        revArea += ` L ${x} ${yZero} Z`;
        payArea += ` L ${x} ${yZero} Z`;
        profArea += ` L ${x} ${yZero} Z`;
      }
    });

    return {
      revenue: revLine,
      payout: payLine,
      profit: profLine,
      revArea,
      payoutArea: payArea,
      profitArea: profArea,
    };
  }, [chartData, getX, getY, yZero]);

  // Guide ticks
  const yTicks = useMemo(() => {
    const ticks = [];
    const count = 4;
    for (let i = 0; i <= count; i++) {
      const val = bounds.min + (yRange * i) / count;
      ticks.push({
        val,
        y: getY(val),
      });
    }
    return ticks;
  }, [bounds, yRange, getY]);

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-zinc-200/80 bg-white/70 p-6 shadow-sm">
        <div className="shimmer mb-4 h-4 w-40 rounded" />
        <div className="shimmer h-[260px] w-full rounded-xl" />
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="flex h-[280px] flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-zinc-200/80 bg-white/50 text-center">
        <Activity className="h-8 w-8 text-zinc-300 animate-pulse" />
        <p className="text-sm font-medium text-zinc-400">
          {t("noTimelineData") || "No timeline aggregation data found"}
        </p>
      </div>
    );
  }

  const hoverItem = hoveredIdx !== null ? chartData[hoveredIdx] : null;

  return (
    <div className="relative rounded-2xl border border-zinc-200/85 bg-white/80 p-6 shadow-sm backdrop-blur-md">
      {/* Header and Toggles */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-zinc-900">
            {t("financeTimelineTitle") || "Interactive Finance Timeline"}
          </h3>
          <p className="text-xs text-zinc-400 mt-0.5">
            {t("periodsCount") || "Aggregated results over"} {chartData.length} {t("periods") || "periods"}
          </p>
        </div>

        {/* Legend Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Revenue Toggle */}
          <button
            onClick={() => setShowRevenue(!showRevenue)}
            className={cn(
              "flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold shadow-sm transition-all duration-300 hover:scale-[1.02]",
              showRevenue
                ? "border-indigo-200 bg-indigo-50/50 text-indigo-700 hover:bg-indigo-50"
                : "border-zinc-200 bg-zinc-50/40 text-zinc-400 hover:bg-zinc-50"
            )}
          >
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                showRevenue ? "bg-indigo-500" : "bg-zinc-300"
              )}
            />
            {t("grossRevenue")}
            {showRevenue ? (
              <Eye size={12} className="opacity-80" />
            ) : (
              <EyeOff size={12} className="opacity-60" />
            )}
          </button>

          {/* Payout Toggle */}
          <button
            onClick={() => setShowPayout(!showPayout)}
            className={cn(
              "flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold shadow-sm transition-all duration-300 hover:scale-[1.02]",
              showPayout
                ? "border-emerald-200 bg-emerald-50/50 text-emerald-700 hover:bg-emerald-50"
                : "border-zinc-200 bg-zinc-50/40 text-zinc-400 hover:bg-zinc-50"
            )}
          >
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                showPayout ? "bg-emerald-500" : "bg-zinc-300"
              )}
            />
            {t("wbForPay")}
            {showPayout ? (
              <Eye size={12} className="opacity-80" />
            ) : (
              <EyeOff size={12} className="opacity-60" />
            )}
          </button>

          {/* Profit Toggle */}
          <button
            onClick={() => setShowProfit(!showProfit)}
            className={cn(
              "flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold shadow-sm transition-all duration-300 hover:scale-[1.02]",
              showProfit
                ? "border-sky-200 bg-sky-50/50 text-sky-700 hover:bg-sky-50"
                : "border-zinc-200 bg-zinc-50/40 text-zinc-400 hover:bg-zinc-50"
            )}
          >
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                showProfit ? "bg-sky-500" : "bg-zinc-300"
              )}
            />
            {t("profitAfterTax")}
            {showProfit ? (
              <Eye size={12} className="opacity-80" />
            ) : (
              <EyeOff size={12} className="opacity-60" />
            )}
          </button>
        </div>
      </div>

      {/* SVG Timeline Canvas */}
      <div className="relative overflow-x-auto">
        <svg
          viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
          className="w-full select-none"
          style={{ minWidth: 600 }}
          aria-label="Finance multiseries timeline chart"
        >
          {/* Definitions for gorgeous gradients */}
          <defs>
            <linearGradient id="grad-revenue" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#6366f1" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="grad-payout" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="grad-profit" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#0ea5e9" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid Guideline ticks (Y) */}
          {yTicks.map((tick, i) => (
            <g key={i} className="opacity-70">
              <line
                x1={PADDING.left}
                x2={CHART_WIDTH - PADDING.right}
                y1={tick.y}
                y2={tick.y}
                stroke="#e4e4e7"
                strokeWidth={1}
                strokeDasharray={i === 0 || i === yTicks.length - 1 ? "" : "3 3"}
              />
              <text
                x={PADDING.left - 12}
                y={tick.y + 3}
                textAnchor="end"
                fontSize={9}
                className="fill-zinc-400 font-medium"
              >
                {formatCompactMoney(tick.val, currency)}
              </text>
            </g>
          ))}

          {/* Zero baseline overlay (if applicable) */}
          {bounds.min < 0 && (
            <line
              x1={PADDING.left}
              x2={CHART_WIDTH - PADDING.right}
              y1={yZero}
              y2={yZero}
              stroke="#a1a1aa"
              strokeWidth={1.2}
              strokeDasharray="4 4"
            />
          )}

          {/* Render Area/Line paths dynamically based on active state */}
          {showRevenue && paths.revArea && (
            <>
              <path d={paths.revArea} fill="url(#grad-revenue)" />
              <path
                d={paths.revenue}
                fill="none"
                stroke="#6366f1"
                strokeWidth={2.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </>
          )}

          {showPayout && paths.payoutArea && (
            <>
              <path d={paths.payoutArea} fill="url(#grad-payout)" />
              <path
                d={paths.payout}
                fill="none"
                stroke="#10b981"
                strokeWidth={2.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </>
          )}

          {showProfit && paths.profitArea && (
            <>
              <path d={paths.profitArea} fill="url(#grad-profit)" />
              <path
                d={paths.profit}
                fill="none"
                stroke="#0ea5e9"
                strokeWidth={2.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </>
          )}

          {/* X Axis Timestamps */}
          {chartData.map((d, i) => {
            const showLabel =
              chartData.length <= 12 ||
              i % Math.ceil(chartData.length / 10) === 0 ||
              i === chartData.length - 1;

            return (
              showLabel && (
                <text
                  key={i}
                  x={getX(i)}
                  y={CHART_HEIGHT - PADDING.bottom + 18}
                  textAnchor="middle"
                  fontSize={9}
                  className="fill-zinc-400 font-medium"
                >
                  {formatDate(d.bucket)}
                </text>
              )
            );
          })}

          {/* Interactivity elements */}
          {chartData.map((d, i) => {
            const x = getX(i);

            return (
              <g key={i}>
                {/* Transparent trigger boundaries */}
                <rect
                  x={x - (CHART_WIDTH - PADDING.left - PADDING.right) / Math.max(chartData.length - 1, 1) / 2}
                  y={PADDING.top}
                  width={(CHART_WIDTH - PADDING.left - PADDING.right) / Math.max(chartData.length - 1, 1)}
                  height={CHART_HEIGHT - PADDING.top - PADDING.bottom}
                  fill="transparent"
                  className="cursor-crosshair"
                  onMouseEnter={() => setHoveredIdx(i)}
                  onMouseLeave={() => setHoveredIdx(null)}
                />
              </g>
            );
          })}

          {/* Highlight indicator lines on hover */}
          {hoveredIdx !== null && (
            <g>
              <line
                x1={getX(hoveredIdx)}
                x2={getX(hoveredIdx)}
                y1={PADDING.top}
                y2={CHART_HEIGHT - PADDING.bottom}
                stroke="#d4d4d8"
                strokeWidth={1}
                strokeDasharray="4 4"
                pointerEvents="none"
              />

              {/* Indicator Circles for hovered values */}
              {showRevenue && (
                <circle
                  cx={getX(hoveredIdx)}
                  cy={getY(chartData[hoveredIdx].revenue)}
                  r={5}
                  fill="#6366f1"
                  stroke="white"
                  strokeWidth={1.5}
                  pointerEvents="none"
                />
              )}
              {showPayout && (
                <circle
                  cx={getX(hoveredIdx)}
                  cy={getY(chartData[hoveredIdx].payout)}
                  r={5}
                  fill="#10b981"
                  stroke="white"
                  strokeWidth={1.5}
                  pointerEvents="none"
                />
              )}
              {showProfit && (
                <circle
                  cx={getX(hoveredIdx)}
                  cy={getY(chartData[hoveredIdx].profit)}
                  r={5}
                  fill="#0ea5e9"
                  stroke="white"
                  strokeWidth={1.5}
                  pointerEvents="none"
                />
              )}
            </g>
          )}
        </svg>
      </div>

      {/* Premium Floating Interactive Tooltip Card */}
      {hoveredIdx !== null && hoverItem && (
        <div
          className="absolute z-30 rounded-xl border border-zinc-200/80 bg-white/95 p-3.5 shadow-xl backdrop-blur-sm transition-all duration-150 pointer-events-none flex flex-col gap-2 min-w-[200px]"
          style={{
            left: `${Math.min(
              Math.max(getX(hoveredIdx) - 100, 20),
              CHART_WIDTH - 220
            )}px`,
            top: `${Math.min(
              Math.max(
                Math.min(
                  showRevenue ? getY(hoverItem.revenue) : CHART_HEIGHT,
                  showPayout ? getY(hoverItem.payout) : CHART_HEIGHT,
                  showProfit ? getY(hoverItem.profit) : CHART_HEIGHT
                ) - 130,
                20
              ),
              CHART_HEIGHT - 80
            )}px`,
          }}
        >
          <div className="border-b border-zinc-100 pb-1.5 flex items-center justify-between">
            <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
              {t("timelineDetail") || "Timeline Point"}
            </span>
            <span className="text-xs font-semibold text-zinc-900 bg-zinc-50 border px-2 py-0.5 rounded-md">
              {formatDate(hoverItem.bucket)}
            </span>
          </div>

          <div className="flex flex-col gap-1.5">
            {showRevenue && (
              <div className="flex items-center justify-between text-xs gap-4">
                <div className="flex items-center gap-1.5 text-zinc-500 font-medium">
                  <span className="h-2 w-2 rounded-full bg-indigo-500" />
                  {t("grossRevenue")}
                </div>
                <span className="font-bold text-zinc-950">
                  {formatMoney(String(hoverItem.revenue), currency)}
                </span>
              </div>
            )}

            {showPayout && (
              <div className="flex items-center justify-between text-xs gap-4">
                <div className="flex items-center gap-1.5 text-zinc-500 font-medium">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  {t("wbForPay")}
                </div>
                <span className="font-bold text-zinc-950">
                  {formatMoney(String(hoverItem.payout), currency)}
                </span>
              </div>
            )}

            {showProfit && (
              <div className="flex items-center justify-between text-xs gap-4">
                <div className="flex items-center gap-1.5 text-zinc-500 font-medium">
                  <span className="h-2 w-2 rounded-full bg-sky-500" />
                  {t("profitAfterTax")}
                </div>
                <span
                  className={cn(
                    "font-bold",
                    hoverItem.profit >= 0 ? "text-emerald-600" : "text-rose-600"
                  )}
                >
                  {formatMoney(String(hoverItem.profit), currency)}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
