"use client";

import React, { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import { ArrowLeft, AlertTriangle } from "lucide-react";
import Link from "next/link";
import { ProductFinanceSettingsTable } from "@/components/finance/ProductFinanceSettingsTable";
import { financeApi } from "@/lib/finance-api";
import { useToast } from "@/contexts/ToastContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useStore } from "@/contexts/StoreContext";
import type { ProductFinanceCatalogFacets, ProductFinanceCatalogItem } from "@/lib/types/finance";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 40;

export default function ProductFinanceSettingsPage() {
  const { error } = useToast();
  const { t } = useLanguage();
  const { currentStoreId } = useStore();
  const storeId = currentStoreId ?? 0;

  const [items, setItems] = useState<ProductFinanceCatalogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [neverSynced, setNeverSynced] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedSubjects, setSelectedSubjects] = useState<string[]>([]);
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [facets, setFacets] = useState<ProductFinanceCatalogFacets>({ brands: [], subjects: [] });

  const deferredSearch = useDeferredValue(search.trim());
  const activeQueryKey = useMemo(
    () => JSON.stringify({ deferredSearch, selectedSubjects, onlyMissing, storeId }),
    [deferredSearch, selectedSubjects, onlyMissing, storeId]
  );

  const fetchSettings = useCallback(async (nextPage = 1, append = false) => {
    if (!storeId) return;
    if (append) {
      setIsLoadingMore(true);
    } else {
      setIsLoading(true);
    }
    try {
      const [data, status] = await Promise.all([
        financeApi.getProductSettingsCatalog(storeId, {
          page: nextPage,
          perPage: PAGE_SIZE,
          search: deferredSearch || undefined,
          subjects: selectedSubjects,
          onlyMissing,
        }),
        financeApi.getSystemStatus(storeId),
      ]);
      setItems((current) => (append ? [...current, ...data.items] : data.items));
      setTotal(data.total);
      setPage(nextPage);
      setHasMore(nextPage * PAGE_SIZE < data.total);
      setFacets(data.facets);
      setNeverSynced(!status.lastSuccessfulProductSyncAt);
    } catch (err) {
      error("Load failed", err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      if (append) {
        setIsLoadingMore(false);
      } else {
        setIsLoading(false);
      }
    }
  }, [deferredSearch, error, onlyMissing, selectedSubjects, storeId]);

  useEffect(() => {
    if (storeId) {
      queueMicrotask(() => {
        void fetchSettings(1, false);
      });
    }
  }, [activeQueryKey, fetchSettings, storeId]);

  useEffect(() => {
    if (!storeId) return;
    const onScroll = () => {
      const scrollHeight = document.documentElement.scrollHeight || 0;
      if (!scrollHeight) return;
      const viewportBottom = window.scrollY + window.innerHeight;
      if (viewportBottom < scrollHeight * 0.7) return;
      if (!hasMore || isLoading || isLoadingMore) return;
      queueMicrotask(() => {
        void fetchSettings(page + 1, true);
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    queueMicrotask(onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [fetchSettings, hasMore, isLoading, isLoadingMore, page, storeId]);

  const toggleSelection = (value: string, setter: React.Dispatch<React.SetStateAction<string[]>>) => {
    setter((current) => (current.includes(value) ? current.filter((item) => item !== value) : [...current, value]));
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <Link
          href="/finance"
          className="rounded-lg p-2 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-950"
        >
          <ArrowLeft size={18} />
        </Link>
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-zinc-950">{t("productCostSettings")}</h1>
          <p className="text-sm text-zinc-500">{t("store")} #{storeId} — {t("productCostSubtitle").toLowerCase()}</p>
        </div>
      </div>

      {!storeId ? (
        <div className="rounded-xl border border-dashed border-zinc-200 bg-white p-10 text-center">
          <p className="text-sm text-zinc-500">{t("selectStoreProducts")}</p>
        </div>
      ) : (
        <>
          {neverSynced && (
            <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
              <AlertTriangle size={15} className="mt-0.5 shrink-0 text-amber-600" />
              <div className="text-sm text-amber-800">
                <span className="font-medium">{t("neverSynced")} </span>
                {t("neverSyncedDesc")}{" "}
                <Link href="/finance" className="underline hover:text-amber-900">
                  {t("financeDashboard")}
                </Link>{" "}
                {t("neverSyncedDesc2")}
              </div>
            </div>
          )}

          <ProductFinanceSettingsTable
            storeId={storeId}
            items={items}
            total={total}
            isLoading={isLoading}
            isLoadingMore={isLoadingMore}
            hasMore={hasMore}
            search={search}
            onlyMissing={onlyMissing}
            selectedSubjects={selectedSubjects}
            facets={facets}
            onSearchChange={setSearch}
            onToggleOnlyMissing={() => setOnlyMissing((current) => !current)}
            onToggleSubject={(value) => toggleSelection(value, setSelectedSubjects)}
            onResetFilters={() => {
              setSearch("");
              setSelectedSubjects([]);
              setOnlyMissing(false);
            }}
            onRefresh={async () => {
              await fetchSettings(1, false);
            }}
          />
        </>
      )}
    </div>
  );
}
