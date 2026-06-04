"use client";

import React, { useMemo, useRef, useState } from "react";
import { Check, ChevronDown, Download, FileSpreadsheet, Filter, Save, Search, Upload, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { financeApi } from "@/lib/finance-api";
import { useToast } from "@/contexts/ToastContext";
import { useLanguage } from "@/contexts/LanguageContext";
import type { ProductFinanceCatalogItem, ProductFinanceCatalogFacets } from "@/lib/types/finance";

interface ProductFinanceSettingsTableProps {
  storeId: number;
  items: ProductFinanceCatalogItem[];
  total: number;
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  search: string;
  onlyMissing: boolean;
  selectedSubjects: string[];
  facets: ProductFinanceCatalogFacets;
  onSearchChange: (value: string) => void;
  onToggleOnlyMissing: () => void;
  onToggleSubject: (value: string) => void;
  onResetFilters: () => void;
  onRefresh: () => Promise<void>;
}

function formatMeta(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function imageUrl(item: ProductFinanceCatalogItem) {
  return item.photoSquareUrl || item.photoBigUrl || "";
}

function normalizeCost(value: string | null | undefined) {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) return "0";
  const numeric = Number(trimmed);
  if (Number.isNaN(numeric)) return trimmed;
  return String(numeric);
}

function displayCost(value: string | null | undefined) {
  const normalized = normalizeCost(value);
  if (!normalized || normalized === "0") return normalized === "0" ? "0" : "";
  const [whole] = normalized.split(".");
  return whole || "0";
}

export function ProductFinanceSettingsTable({
  storeId,
  items,
  total,
  isLoading,
  isLoadingMore,
  hasMore,
  search,
  onlyMissing,
  selectedSubjects,
  facets,
  onSearchChange,
  onToggleOnlyMissing,
  onToggleSubject,
  onResetFilters,
  onRefresh,
}: ProductFinanceSettingsTableProps) {
  const { t } = useLanguage();
  const { success, error } = useToast();
  const [isImporting, setIsImporting] = useState(false);
  const [isSavingAll, setIsSavingAll] = useState(false);
  const [subjectMenuOpen, setSubjectMenuOpen] = useState(false);
  const [isExcelModalOpen, setIsExcelModalOpen] = useState(false);
  const [isPreparingDocument, setIsPreparingDocument] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const [preparedDownloadUrl, setPreparedDownloadUrl] = useState<string | null>(null);
  const [preparedFileName, setPreparedFileName] = useState("product-finance-prepared.xlsx");
  const [inlineValues, setInlineValues] = useState<Record<number, string>>({});
  const fileRef = useRef<HTMLInputElement>(null);

  const changedItems = useMemo(
    () =>
      items
        .map((item) => {
          const currentValue = inlineValues[item.productId];
          if (currentValue === undefined) return null;
          return normalizeCost(currentValue) !== normalizeCost(item.costPrice)
            ? { product_id: item.productId, cost_price: currentValue }
            : null;
        })
        .filter((item): item is { product_id: number; cost_price: string } => item !== null),
    [inlineValues, items]
  );

  const changedIds = useMemo(() => new Set(changedItems.map((item) => item.product_id)), [changedItems]);

  const saveAll = async () => {
    if (!changedItems.length) return;
    const invalidRow = changedItems.find((item) => Number.isNaN(Number(item.cost_price)));
    if (invalidRow) {
      error(t("error"), `${t("invalidCostValue")} #${invalidRow.product_id}`);
      return;
    }
    setIsSavingAll(true);
    try {
      await financeApi.updateProductSettingsBulk(storeId, changedItems);
      success(t("save"), `${changedItems.length} ${t("productCostSavedBulk")}`);
      setInlineValues({});
      await onRefresh();
    } catch (err) {
      error(t("error"), err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsSavingAll(false);
    }
  };

  const resetImportState = () => {
    setSelectedFile(null);
    setIsDragActive(false);
    if (fileRef.current) {
      fileRef.current.value = "";
    }
  };

  const clearPreparedDocument = () => {
    if (preparedDownloadUrl) {
      URL.revokeObjectURL(preparedDownloadUrl);
    }
    setPreparedDownloadUrl(null);
    setPreparedFileName("product-finance-prepared.xlsx");
  };

  const validateExcelFile = (file: File | null) => {
    if (!file) {
      error(t("error"), t("excelOnly"));
      return false;
    }
    if (!file.name.toLowerCase().endsWith(".xlsx")) {
      error(t("error"), t("excelOnly"));
      return false;
    }
    return true;
  };

  const handleFileSelected = (file: File | null) => {
    if (!file) return;
    if (!validateExcelFile(file)) {
      resetImportState();
      return;
    }
    setSelectedFile(file);
  };

  const handleImport = async () => {
    if (!validateExcelFile(selectedFile)) return;
    setIsImporting(true);
    try {
      const result = await financeApi.importSettings(storeId, selectedFile!);
      if (result.errors.length) {
        error(
          t("importCompletedWithErrors"),
          result.errors.slice(0, 5).map((entry) => `#${entry.row}: ${entry.error}`).join(" | ")
        );
      } else {
        success(t("importExcel"), t("importSuccessReloaded"));
        setIsExcelModalOpen(false);
      }
      setInlineValues({});
      await onRefresh();
    } catch (err) {
      error(t("error"), err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsImporting(false);
      resetImportState();
    }
  };

  const prepareDocument = async () => {
    setIsPreparingDocument(true);
    try {
      clearPreparedDocument();
      const response = await fetch(financeApi.getExportTemplateUrl(storeId, "prepared"), {
        credentials: "include",
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || "Failed to prepare document");
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const disposition = response.headers.get("content-disposition") || "";
      const filenameMatch = disposition.match(/filename=([^;]+)/i);
      const nextFileName = filenameMatch?.[1]?.replace(/"/g, "").trim() || "product-finance-prepared.xlsx";
      setPreparedDownloadUrl(objectUrl);
      setPreparedFileName(nextFileName);
      success("Excel", t("documentPrepared"));
    } catch (err) {
      error(t("error"), err instanceof Error ? err.message : "Failed to prepare document");
    } finally {
      setIsPreparingDocument(false);
    }
  };

  const downloadPreparedDocument = () => {
    if (!preparedDownloadUrl) return;
    const link = document.createElement("a");
    link.href = preparedDownloadUrl;
    link.download = preparedFileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const activeFilterCount = selectedSubjects.length + (onlyMissing ? 1 : 0);

  return (
    <>
    <div className="rounded-2xl border border-zinc-200 bg-white shadow-soft-sm">
      <div className="border-b border-zinc-100 px-4 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-1 flex-col gap-3 md:flex-row md:items-center">
            <div className="relative w-full md:max-w-[360px]">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                value={search}
                onChange={(event) => onSearchChange(event.target.value)}
                placeholder={t("searchCostProducts")}
                className="h-10 w-full rounded-xl border border-zinc-300 bg-white pl-9 pr-9 text-sm text-zinc-900 outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-indigo-100"
              />
              {search && (
                <button
                  onClick={() => onSearchChange("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 transition-colors hover:text-zinc-700"
                >
                  <X size={14} />
                </button>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Button variant="outline" size="sm" onClick={() => setSubjectMenuOpen((current) => !current)}>
                  <Filter size={14} />
                  {t("subjects")}
                  {selectedSubjects.length ? ` (${selectedSubjects.length})` : ""}
                  <ChevronDown size={14} />
                </Button>
                {subjectMenuOpen && (
                  <div className="absolute left-0 top-full z-20 mt-2 max-h-72 w-64 overflow-y-auto rounded-xl border border-zinc-200 bg-white p-2 shadow-soft-xl">
                    {facets.subjects.map((subject) => {
                      const active = selectedSubjects.includes(subject);
                      return (
                        <button
                          key={subject}
                          onClick={() => onToggleSubject(subject)}
                          className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm text-zinc-700 hover:bg-zinc-50"
                        >
                          <span className="truncate">{subject}</span>
                          {active ? <Check size={14} className="text-emerald-600" /> : null}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              <Button variant={onlyMissing ? "brand" : "outline"} size="sm" onClick={onToggleOnlyMissing}>
                {t("onlyMissingCosts")}
              </Button>

              {activeFilterCount > 0 ? (
                <Button variant="ghost" size="sm" onClick={onResetFilters}>
                  {t("resetFilters")}
                </Button>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-zinc-500">{total} {t("productsTotalCount")}</span>
            <Button
              variant="brand"
              size="sm"
              onClick={() => void saveAll()}
              isLoading={isSavingAll}
              disabled={!changedItems.length}
            >
              <Save size={14} />
              {t("saveAll")}
              {changedItems.length ? ` (${changedItems.length})` : ""}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsExcelModalOpen(true)}
            >
              <FileSpreadsheet size={14} />
              Excel
            </Button>
          </div>
        </div>

        {changedItems.length ? (
          <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {changedItems.length} {t("unsavedChanges")}
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-[84px_minmax(320px,1.9fr)_180px] gap-3 border-b border-zinc-100 bg-zinc-50 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">
        <div>{t("image")}</div>
        <div>{t("product")}</div>
        <div>{t("costPrice")}</div>
      </div>

      {isLoading && items.length === 0 ? (
        <div className="space-y-3 px-4 py-4">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="grid grid-cols-[84px_minmax(320px,1.9fr)_180px] gap-3">
              <div className="shimmer h-16 rounded-xl" />
              <div className="shimmer h-16 rounded-xl" />
              <div className="shimmer h-16 rounded-xl" />
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="px-4 py-16 text-center text-sm text-zinc-500">
          {t("noProductsFound")}
        </div>
      ) : (
        <div className="divide-y divide-zinc-100">
          {items.map((item) => {
            const image = imageUrl(item);
            const inlineValue = inlineValues[item.productId] ?? displayCost(item.costPrice);
            const isChanged = changedIds.has(item.productId);
            return (
              <div key={item.productId} className="grid grid-cols-[84px_minmax(320px,1.9fr)_180px] gap-3 px-4 py-3">
                <div className="flex items-center">
                  {image ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={image} alt={item.title || `nmId ${item.nmId}`} className="h-16 w-16 rounded-xl object-cover ring-1 ring-zinc-200" loading="lazy" />
                  ) : (
                    <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-zinc-100 text-xs text-zinc-400">
                      {t("noImage")}
                    </div>
                  )}
                </div>

                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-zinc-900">{item.title || `${t("product")} #${item.productId}`}</div>
                  <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-zinc-500">
                    <span>{t("subjectName")}: {formatMeta(item.subjectName)}</span>
                    <span>nmId: {formatMeta(item.nmId)}</span>
                    <span>{t("vendorCode")}: {formatMeta(item.vendorCode)}</span>
                    <span>{t("brands")}: {formatMeta(item.brand)}</span>
                  </div>
                </div>

                <div className="flex items-center">
                  <Input
                    value={inlineValue}
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setInlineValues((current) => {
                        if (normalizeCost(nextValue) === normalizeCost(displayCost(item.costPrice))) {
                          const next = { ...current };
                          delete next[item.productId];
                          return next;
                        }
                        return { ...current, [item.productId]: nextValue };
                      });
                    }}
                    inputMode="decimal"
                    placeholder="0"
                    className={isChanged ? "border-amber-300 focus:border-amber-400 focus:ring-amber-100" : undefined}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {isLoadingMore ? (
        <div className="px-4 py-4 text-center text-sm text-zinc-500">{t("loading")}</div>
      ) : hasMore ? (
        <div className="px-4 py-4 text-center text-xs text-zinc-400">{t("scrollToLoadMore")}</div>
      ) : items.length > 0 ? (
        <div className="px-4 py-4 text-center text-xs text-zinc-400">{t("allProductsLoaded")}</div>
      ) : null}
    </div>
    <Modal
      isOpen={isExcelModalOpen}
      onClose={() => {
        setIsExcelModalOpen(false);
        resetImportState();
        clearPreparedDocument();
      }}
      title="Excel"
      description={t("excelUploadDesc")}
      className="max-w-xl"
    >
      <div className="space-y-4">
        <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-600">
          {t("excelPreparedDesc")}
        </div>
        <div className="flex flex-wrap gap-3">
          <Button
            variant="brand"
            onClick={() => void prepareDocument()}
            isLoading={isPreparingDocument}
          >
            <FileSpreadsheet size={14} />
            {t("prepareDocument")}
          </Button>
          <Button
            variant="outline"
            onClick={downloadPreparedDocument}
            disabled={!preparedDownloadUrl}
          >
            <Download size={14} />
            {t("downloadPrepared")}
          </Button>
        </div>

        {preparedDownloadUrl ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            {t("documentPreparedReady")}
          </div>
        ) : null}

        <input
          ref={fileRef}
          type="file"
          accept=".xlsx"
          className="hidden"
          onChange={(event) => handleFileSelected(event.target.files?.[0] ?? null)}
        />

        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragActive(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setIsDragActive(false);
          }}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragActive(false);
            handleFileSelected(event.dataTransfer.files?.[0] ?? null);
          }}
          className={`flex min-h-40 w-full flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-8 text-center transition-colors ${
            isDragActive
              ? "border-indigo-400 bg-indigo-50 text-indigo-700"
              : "border-zinc-300 bg-zinc-50 text-zinc-600 hover:border-zinc-400 hover:bg-zinc-100"
          }`}
        >
          <Upload size={26} />
          <div className="space-y-1">
            <div className="text-sm font-medium">{t("dropExcelHere")}</div>
            <div className="text-xs text-zinc-500">{t("excelOnly")}</div>
          </div>
        </button>

        {selectedFile ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            {t("selectedFile")}: {selectedFile.name}
          </div>
        ) : null}

        <div className="flex justify-end gap-3">
          <Button
            variant="ghost"
            onClick={() => {
              setIsExcelModalOpen(false);
              resetImportState();
              clearPreparedDocument();
            }}
          >
            {t("cancel")}
          </Button>
          <Button
            variant="brand"
            onClick={() => void handleImport()}
            isLoading={isImporting}
            disabled={!selectedFile}
          >
            <Upload size={14} />
            {t("updateCostPrices")}
          </Button>
        </div>
      </div>
    </Modal>
    </>
  );
}
