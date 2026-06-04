"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw, AlertTriangle, Store, BarChart2, Sparkles } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { CooldownAlert } from "@/components/finance/CooldownAlert";
import { FinanceSummaryCards } from "@/components/finance/FinanceSummaryCards";
import { FinanceTimelineChart } from "@/components/finance/FinanceTimelineChart";
import { ProductBreakdownTable } from "@/components/finance/ProductBreakdownTable";
import { FinanceCostBreakdownSection } from "@/components/finance/FinanceCostBreakdownSection";
import { FinanceInsightsPanel } from "@/components/finance/FinanceInsightsPanel";
import { GeminiAnalysisPanel } from "@/components/finance/GeminiAnalysisPanel";
import { FinanceDateRangeFilter } from "@/components/finance/FinanceDateRangeFilter";
import { FinanceSystemStatusCard } from "@/components/finance/FinanceSystemStatusCard";
import { SyncStatusBadge } from "@/components/finance/SyncStatusBadge";
import { financeApi } from "@/lib/finance-api";
import { useToast } from "@/contexts/ToastContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useStore } from "@/contexts/StoreContext";
import { defaultDateFrom, defaultDateTo } from "@/lib/finance-utils";
import type {
  FinanceSystemStatus,
  FinanceSummary,
  FinanceTimelinePoint,
  FinanceProductBreakdownItem,
  FinanceCostBreakdown,
  FinanceInsight,
  GeminiSnapshotItem,
  GroupBy,
  ProductSyncStatus,
  FinanceSyncStatus,
} from "@/lib/types/finance";

export const dynamic = "force-dynamic";

export default function FinanceDashboardPage() {
  const { error, success } = useToast();
  const { t } = useLanguage();
  const { currentStoreId } = useStore();
  const storeId = currentStoreId ?? 0;

  const [dateFrom, setDateFrom] = useState(defaultDateFrom());
  const [dateTo, setDateTo] = useState(defaultDateTo());
  const [groupBy, setGroupBy] = useState<GroupBy>("day");
  const [breakdownPage, setBreakdownPage] = useState(1);
  const [breakdownHasMore, setBreakdownHasMore] = useState(false);

  const [systemStatus, setSystemStatus] = useState<FinanceSystemStatus | null>(null);
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [timeline, setTimeline] = useState<FinanceTimelinePoint[]>([]);
  const [breakdown, setBreakdown] = useState<FinanceProductBreakdownItem[]>([]);
  const [breakdownTotal, setBreakdownTotal] = useState(0);
  const [costBreakdown, setCostBreakdown] = useState<FinanceCostBreakdown | null>(null);
  const [insights, setInsights] = useState<FinanceInsight[]>([]);
  const [snapshots, setSnapshots] = useState<GeminiSnapshotItem[]>([]);
  const [productSyncStatus, setProductSyncStatus] = useState<ProductSyncStatus | null>(null);
  const [financeSyncStatus, setFinanceSyncStatus] = useState<FinanceSyncStatus | null>(null);

  const [loadingData, setLoadingData] = useState(false);
  const [loadingBreakdown, setLoadingBreakdown] = useState(false);
  const [loadingBreakdownMore, setLoadingBreakdownMore] = useState(false);
  const [syncingProducts, setSyncingProducts] = useState(false);
  const [syncingFinance, setSyncingFinance] = useState(false);

  const fetchStatus = useCallback(async () => {
    if (!storeId) return;
    try {
      const [status, pSync, fSync] = await Promise.all([
        financeApi.getSystemStatus(storeId),
        financeApi.getProductSyncStatus(storeId),
        financeApi.getFinanceSyncStatus(storeId, { date_from: dateFrom, date_to: dateTo }),
      ]);
      setSystemStatus(status);
      setProductSyncStatus(pSync);
      setFinanceSyncStatus(fSync);
    } catch (err) {
      error("Status error", err instanceof Error ? err.message : "Failed to load system status");
    } finally {
    }
  }, [storeId, dateFrom, dateTo, error]);

  const fetchReportData = useCallback(async () => {
    if (!storeId) return;
    setLoadingData(true);
    try {
      const [sum, tl, cb, ins] = await Promise.all([
        financeApi.getSummary(storeId, dateFrom, dateTo),
        financeApi.getTimeline(storeId, dateFrom, dateTo, groupBy),
        financeApi.getCostBreakdown(storeId, dateFrom, dateTo),
        financeApi.getInsights(storeId, dateFrom, dateTo),
      ]);
      setSummary(sum);
      setTimeline(tl.items);
      setCostBreakdown(cb);
      setInsights(ins.items);
    } catch (err) {
      error("Data error", err instanceof Error ? err.message : "Failed to load finance data");
    } finally {
      setLoadingData(false);
    }
  }, [storeId, dateFrom, dateTo, groupBy, error]);

  const fetchBreakdown = useCallback(async (nextPage = 1, append = false) => {
    if (!storeId) return;
    if (append) {
      setLoadingBreakdownMore(true);
    } else {
      setLoadingBreakdown(true);
    }
    try {
      const pb = await financeApi.getProductBreakdown(storeId, {
        date_from: dateFrom,
        date_to: dateTo,
        page: nextPage,
        perPage: 50,
        sort: "profitAfterTax",
        order: "desc",
      });
      setBreakdown((current) => (append ? [...current, ...pb.items] : pb.items));
      setBreakdownTotal(pb.total);
      setBreakdownPage(nextPage);
      setBreakdownHasMore(nextPage * pb.perPage < pb.total);
    } catch (err) {
      error("Data error", err instanceof Error ? err.message : "Failed to load finance data");
    } finally {
      if (append) {
        setLoadingBreakdownMore(false);
      } else {
        setLoadingBreakdown(false);
      }
    }
  }, [dateFrom, dateTo, error, storeId]);

  const fetchSnapshots = useCallback(async () => {
    if (!storeId) return;
    try {
      const snaps = await financeApi.getGeminiSnapshots(storeId);
      setSnapshots(snaps.items);
    } catch {
      // Non-critical
    }
  }, [storeId]);

  useEffect(() => {
    if (storeId) {
      queueMicrotask(() => { void fetchStatus(); });
    }
  }, [storeId, fetchStatus]);

  useEffect(() => {
    if (storeId) {
      queueMicrotask(() => {
        void fetchReportData();
        void fetchBreakdown(1, false);
        void fetchSnapshots();
      });
    }
  }, [storeId, fetchBreakdown, fetchReportData, fetchSnapshots]);

  useEffect(() => {
    if (!storeId) return;
    const onScroll = () => {
      const scrollHeight = document.documentElement.scrollHeight || 0;
      if (!scrollHeight) return;
      const viewportBottom = window.scrollY + window.innerHeight;
      if (viewportBottom < scrollHeight * 0.7) return;
      if (!breakdownHasMore || loadingBreakdown || loadingBreakdownMore) return;
      queueMicrotask(() => {
        void fetchBreakdown(breakdownPage + 1, true);
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    queueMicrotask(onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [breakdownHasMore, breakdownPage, fetchBreakdown, loadingBreakdown, loadingBreakdownMore, storeId]);

  // Polling for sync status unconditionally every 6 seconds to keep the UI in sync
  useEffect(() => {
    if (!storeId) return;
    const timer = setInterval(() => {
      queueMicrotask(() => {
        void fetchStatus();
      });
    }, 6000);
    return () => clearInterval(timer);
  }, [fetchStatus, storeId]);

  // Keep track of sync state transitions to automatically refresh when synchronization finishes
  const prevProductStatusRef = useRef<string | null>(null);
  const prevFinanceStatusRef = useRef<string | null>(null);

  useEffect(() => {
    if (!storeId) return;
    const currentProductStatus = productSyncStatus?.status || null;
    const prevProductStatus = prevProductStatusRef.current;

    // Refresh active report & snapshot immediately if product sync has successfully finished
    if (prevProductStatus === "running" && currentProductStatus !== "running") {
      queueMicrotask(() => {
        void fetchReportData();
        void fetchBreakdown(1, false);
        void fetchSnapshots();
      });
      success("Product catalog synchronized and updated!");
    }

    prevProductStatusRef.current = currentProductStatus;
  }, [productSyncStatus?.status, storeId, fetchBreakdown, fetchReportData, fetchSnapshots, success]);

  useEffect(() => {
    if (!storeId) return;
    const currentFinanceStatus = financeSyncStatus?.status || null;
    const prevFinanceStatus = prevFinanceStatusRef.current;

    // Refresh active report & snapshot immediately if finance sync has successfully finished
    if (prevFinanceStatus === "running" && currentFinanceStatus !== "running") {
      queueMicrotask(() => {
        void fetchReportData();
        void fetchBreakdown(1, false);
        void fetchSnapshots();
      });
      success("Financial reports synchronized and updated!");
    }

    prevFinanceStatusRef.current = currentFinanceStatus;
  }, [financeSyncStatus?.status, storeId, fetchBreakdown, fetchReportData, fetchSnapshots, success]);

  const handleProductSync = async () => {
    if (!storeId) return;
    if (systemStatus?.contentApi.inCooldown) {
      error("Cooldown active", "Content API is in cooldown. Please wait.");
      return;
    }
    setSyncingProducts(true);
    try {
      await financeApi.triggerProductSync(storeId);
      await fetchStatus();
    } catch (err) {
      error("Product sync failed", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSyncingProducts(false);
    }
  };

  const handleFinanceSync = async () => {
    if (!storeId) return;
    if (systemStatus?.financeApi.inCooldown) {
      error("Cooldown active", "Finance API is in cooldown. Please wait.");
      return;
    }
    setSyncingFinance(true);
    try {
      await financeApi.triggerFinanceSync(storeId, {
        date_from: dateFrom,
        date_to: dateTo,
        period: "daily",
      });
      await fetchStatus();
      await fetchReportData();
      await fetchBreakdown(1, false);
    } catch (err) {
      error("Finance sync failed", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSyncingFinance(false);
    }
  };

  const productSyncDisabled =
    syncingProducts ||
    productSyncStatus?.status === "running" ||
    systemStatus?.contentApi.inCooldown === true;

  const financeSyncDisabled =
    syncingFinance ||
    financeSyncStatus?.status === "running" ||
    systemStatus?.financeApi.inCooldown === true;

  if (!storeId) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
        <Store size={36} className="text-zinc-300" />
        <h2 className="text-lg font-medium text-zinc-700">{t("storeNotSelected")}</h2>
        <p className="max-w-sm text-sm text-zinc-500">{t("storeNotSelectedDesc")}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 pb-10">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-150 pb-5">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-zinc-900 sm:text-4xl">
            {t("financeTitle")}
          </h1>
          <p className="mt-1 text-sm font-medium text-zinc-400">
            {t("financeSubtitle")} <span className="text-zinc-600 bg-zinc-100 px-2 py-0.5 rounded-md font-mono text-xs">#{storeId}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <Link href="/finance/settings">
            <Button variant="outline" size="sm" className="shadow-sm hover:bg-zinc-50">
              {t("settings")}
            </Button>
          </Link>
          <Link href="/finance/product-settings">
            <Button variant="outline" size="sm" className="shadow-sm hover:bg-zinc-50">
              {t("productCosts")}
            </Button>
          </Link>
        </div>
      </div>

      {/* Cooldown alerts */}
      {systemStatus?.contentApi.inCooldown && (
        <CooldownAlert cooldowns={systemStatus.contentApi.cooldowns} category="content" />
      )}
      {systemStatus?.financeApi.inCooldown && (
        <CooldownAlert cooldowns={systemStatus.financeApi.cooldowns} category="finance" />
      )}

      {/* Missing settings warning */}
      {systemStatus?.hasProductsMissingFinanceSettings && (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50/50 p-4 shadow-sm backdrop-blur-sm">
          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-600 animate-bounce" />
          <div className="min-w-0 flex-1 text-sm">
            <span className="font-semibold text-amber-800">
              {systemStatus.missingFinanceSettingsCount} {t("missingSettings")}{" "}
            </span>
            <Link
              href="/finance/product-settings"
              className="underline font-semibold text-amber-700 hover:text-amber-900 transition-colors"
            >
              {t("configureThem")}
            </Link>{" "}
            <span className="text-amber-750 font-medium">{t("improveAccuracy")}</span>
          </div>
        </div>
      )}

      {/* Unmapped rows warning */}
      {systemStatus?.hasUnmappedFinanceRows && (
        <div className="flex items-start gap-3 rounded-2xl border border-zinc-200 bg-zinc-50/70 p-4 shadow-sm">
          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-zinc-500" />
          <p className="text-sm font-medium text-zinc-650">
            {systemStatus.unmappedFinanceRowsCount} {t("unmappedRows")}
          </p>
        </div>
      )}

      {/* Filters + Sync controls */}
      <div className="flex flex-wrap items-end justify-between gap-6 rounded-2xl border border-zinc-200/80 bg-white/70 p-5 shadow-sm backdrop-blur-md">
        <FinanceDateRangeFilter
          dateFrom={dateFrom}
          dateTo={dateTo}
          groupBy={groupBy}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
          onGroupByChange={setGroupBy}
        />

        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">{t("productSync")}</span>
            <div className="flex items-center gap-2">
              <SyncStatusBadge status={productSyncStatus?.status} />
              <Button
                variant="outline"
                size="sm"
                className="shadow-sm font-semibold"
                onClick={handleProductSync}
                disabled={productSyncDisabled}
                isLoading={syncingProducts || productSyncStatus?.status === "running"}
              >
                {t("syncProducts")}
              </Button>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">{t("financeSync")}</span>
            <div className="flex items-center gap-2">
              <SyncStatusBadge status={financeSyncStatus?.status} />
              <Button
                variant="brand"
                size="sm"
                className="shadow-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 border-indigo-700"
                onClick={handleFinanceSync}
                disabled={financeSyncDisabled}
                isLoading={syncingFinance || financeSyncStatus?.status === "running"}
              >
                {t("syncFinance")}
              </Button>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="rounded-xl border border-zinc-200 hover:bg-zinc-50"
            onClick={() => { void fetchStatus(); void fetchReportData(); void fetchBreakdown(1, false); }}
            isLoading={loadingData || loadingBreakdown}
            title={t("refreshData")}
          >
            <RefreshCw size={15} />
          </Button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-col gap-8">
        {/* Summary cards */}
        <FinanceSummaryCards
          summary={summary}
          isLoading={loadingData}
        />

        {/* Timeline chart */}
        <FinanceTimelineChart
          items={timeline}
          isLoading={loadingData}
        />

        {/* Product breakdown + sidebar in grid */}
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_300px]">
          <div className="flex flex-col gap-6">
            {/* Product breakdown table */}
            <div>
              <div className="mb-3.5 flex items-center gap-2">
                <BarChart2 size={16} className="text-zinc-400" />
                <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-450">{t("productBreakdown")}</h2>
              </div>
            <ProductBreakdownTable
              items={breakdown}
              total={breakdownTotal}
              isLoading={loadingData || loadingBreakdown}
              isLoadingMore={loadingBreakdownMore}
              hasMore={breakdownHasMore}
            />
            </div>

            {/* Gemini analysis */}
            <div className="rounded-2xl border border-zinc-200/80 bg-white/70 p-6 shadow-sm backdrop-blur-md">
              <div className="mb-4 flex items-center gap-2">
                <Sparkles size={16} className="text-indigo-500 animate-pulse" />
                <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-800">{t("aiAnalysis")}</h2>
              </div>
              <GeminiAnalysisPanel
                storeId={storeId}
                dateFrom={dateFrom}
                dateTo={dateTo}
                groupBy={groupBy}
                geminiConfigured={systemStatus?.geminiConfigured ?? false}
                snapshots={snapshots}
                onSnapshotsRefresh={fetchSnapshots}
              />
            </div>
          </div>

          {/* Right sidebar: Insights + Cost Breakdown */}
          <div className="flex flex-col gap-6">
            <FinanceSystemStatusCard
              status={systemStatus}
              isLoading={loadingData}
              onRefresh={() => {
                void fetchStatus();
                void fetchBreakdown(1, false);
              }}
            />

            <div className="rounded-2xl border border-zinc-200/80 bg-white/70 p-6 shadow-sm backdrop-blur-md">
              <div className="mb-4 flex items-center gap-2">
                <BarChart2 size={16} className="text-zinc-400" />
                <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-800">{t("insights")}</h2>
              </div>
              <FinanceInsightsPanel
                insights={insights}
                isLoading={loadingData}
              />
            </div>

            <FinanceCostBreakdownSection
              breakdown={costBreakdown}
              isLoading={loadingData}
            />
          </div>
        </div>
      </div>

      {loadingData && !summary && (
        <div className="flex items-center justify-center py-12">
          <Spinner size="lg" />
        </div>
      )}
    </div>
  );
}
