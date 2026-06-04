"use client";

import React, { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Settings } from "lucide-react";
import Link from "next/link";
import { SellerFinanceSettingsForm } from "@/components/finance/SellerFinanceSettingsForm";
import { financeApi } from "@/lib/finance-api";
import { useToast } from "@/contexts/ToastContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useStore } from "@/contexts/StoreContext";
import type { SellerFinanceSettings } from "@/lib/types/finance";

export const dynamic = "force-dynamic";

export default function SellerFinanceSettingsPage() {
  const { error } = useToast();
  const { t } = useLanguage();
  const { currentStoreId } = useStore();
  const storeId = currentStoreId ?? 0;

  const [settings, setSettings] = useState<SellerFinanceSettings | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchSettings = useCallback(async () => {
    if (!storeId) return;
    setIsLoading(true);
    try {
      const data = await financeApi.getSellerSettings(storeId);
      setSettings(data);
    } catch (err) {
      error("Load failed", err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setIsLoading(false);
    }
  }, [storeId, error]);

  useEffect(() => {
    queueMicrotask(() => { void fetchSettings(); });
  }, [fetchSettings]);

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6 flex items-center gap-3">
        <Link
          href="/finance"
          className="rounded-lg p-2 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-950"
        >
          <ArrowLeft size={18} />
        </Link>
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-zinc-950">{t("financeSettingsTitle")}</h1>
          <p className="text-sm text-zinc-500">{t("store")} #{storeId} — {t("financeSettingsSubtitle").toLowerCase()}</p>
        </div>
        <Settings size={20} className="ml-auto text-zinc-300" />
      </div>

      {!storeId ? (
        <div className="rounded-xl border border-dashed border-zinc-200 bg-white p-10 text-center">
          <p className="text-sm text-zinc-500">{t("selectStoreSettings")}</p>
        </div>
      ) : (
        <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
          <p className="mb-6 text-sm text-zinc-500">{t("financeSettingsDesc")}</p>
          <SellerFinanceSettingsForm
            storeId={storeId}
            settings={settings}
            isLoading={isLoading}
            onSaved={setSettings}
          />
        </div>
      )}
    </div>
  );
}
