"use client";

import React, { useEffect, useState } from "react";
import { BarChart2, ListChecks, Plus, Settings, Store, Sparkles } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { CreateStoreModal } from "@/components/dashboard/CreateStoreModal";
import { Spinner } from "@/components/ui/Spinner";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useStore } from "@/contexts/StoreContext";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type UsageSummary = {
  plan_type: string;
  monthly_quota: number;
  used_quota: number;
  remaining_quota: number;
  quota_percent: number;
  monthly_cost_limit: number | null;
  used_cost: number;
  remaining_cost: number | null;
  cost_percent: number | null;
  max_images_per_job: number;
  allow_legacy_vton: boolean;
  allow_gpt_image: boolean;
  priority_queue: boolean;
  credit_balance: number;
  credits_used: number;
  credits_granted: number;
  quota_reset_at: string | null;
};

function getGreeting(t: (k: string) => string) {
  const h = new Date().getHours();
  if (h < 12) return t("goodMorning");
  if (h < 18) return t("goodAfternoon");
  return t("goodEvening");
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const { stores, currentStoreId, isLoading, addStore } = useStore();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [usage, setUsage] = useState<UsageSummary | null>(null);

  const activeStore = stores.find((s) => s.id === currentStoreId) ?? null;
  const noStores = !isLoading && stores.length === 0;

  useEffect(() => {
    if (noStores) queueMicrotask(() => setIsCreateOpen(true));
  }, [noStores]);

  useEffect(() => {
    api.get("/auth/usage")
      .then((response) => setUsage(response as UsageSummary))
      .catch(() => setUsage(null));
  }, []);

  const handleStoreCreated = (store: { id: number; name: string }) => {
    addStore(store);
    setIsCreateOpen(false);
  };

  if (isLoading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }


  if (noStores) {
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-24 text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-brand/10">
          <Store size={36} className="text-brand" />
        </div>
        <div className="max-w-sm">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-950">{t("welcomeTitle")}</h1>
          <p className="mt-2 text-sm text-zinc-500">{t("welcomeDesc")}</p>
        </div>
        <Button variant="brand" onClick={() => setIsCreateOpen(true)}>
          <Plus size={16} className="mr-2" />
          {t("connectFirstStore")}
        </Button>
        <CreateStoreModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} onSuccess={handleStoreCreated} />
      </div>
    );
  }

  const sid = activeStore?.id;

  const tiles = [
    {
      icon: ListChecks,
      color: "bg-indigo-50 text-indigo-600",
      title: t("viewCards"),
      desc: t("viewCardsDesc"),
      href: sid ? `/cards?store_id=${sid}` : "/cards",
    },
    {
      icon: Sparkles,
      color: "bg-violet-50 text-violet-600",
      title: t("createCard"),
      desc: t("createCardDesc"),
      href: sid ? `/cards/new?store_id=${sid}` : "/cards/new",
    },
    {
      icon: BarChart2,
      color: "bg-emerald-50 text-emerald-600",
      title: t("viewFinance"),
      desc: t("viewFinanceDesc"),
      href: "/finance",
    },
    {
      icon: Settings,
      color: "bg-zinc-100 text-zinc-600",
      title: t("viewSettings"),
      desc: t("viewSettingsDesc"),
      href: "/settings",
    },
  ];

  return (
    <div className="mx-auto max-w-3xl">
      {/* Greeting */}
      <div className="mb-8">
        <p className="text-sm font-medium text-zinc-400">{getGreeting(t)},</p>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-950">{user?.name}</h1>
        {activeStore && (
          <div className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs text-zinc-500 shadow-soft-sm">
            <Store size={11} className="text-zinc-400" />
            <span className="font-medium text-zinc-700">{activeStore.name}</span>
          </div>
        )}
        {usage && (
          <div className="mt-4 rounded-2xl border border-zinc-200 bg-white p-4 shadow-soft-sm">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium text-zinc-700">Plan {usage.plan_type.toUpperCase()}</span>
              <span className="text-zinc-500">{usage.used_quota} / {usage.monthly_quota}</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-zinc-200">
              <div className="h-full rounded-full bg-brand" style={{ width: `${Math.min(100, usage.quota_percent)}%` }} />
            </div>
            <p className="mt-2 text-xs text-zinc-500">Remaining: {usage.remaining_quota} generated images this cycle.</p>
            <p className="mt-1 text-xs text-zinc-500">
              Max/job: {usage.max_images_per_job} · GPT image: {usage.allow_gpt_image ? "enabled" : "disabled"} · Legacy VTON: {usage.allow_legacy_vton ? "enabled" : "disabled"}
            </p>
            <p className="mt-1 text-xs text-zinc-500">
              Next reset: {usage.quota_reset_at ? new Date(usage.quota_reset_at).toLocaleDateString() : "Not scheduled"}
            </p>
            <p className="mt-1 text-xs text-zinc-500">
              Credits: {usage.credit_balance} available · {usage.credits_used} used this cycle
            </p>
            {usage.monthly_quota > 0 && usage.used_quota >= usage.monthly_quota && (
              <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                Upgrade plan or contact admin.
              </div>
            )}
            {usage.monthly_cost_limit !== null && usage.used_cost >= usage.monthly_cost_limit && (
              <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                Upgrade plan or contact admin.
              </div>
            )}
            {usage.monthly_quota > 0 && usage.used_quota / usage.monthly_quota >= 0.8 && usage.used_quota < usage.monthly_quota && (
              <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                You are close to your monthly image limit.
              </div>
            )}
            {usage.monthly_cost_limit !== null && usage.monthly_cost_limit > 0 && usage.used_cost / usage.monthly_cost_limit >= 0.8 && usage.used_cost < usage.monthly_cost_limit && (
              <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                You are close to your monthly cost limit.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Quick actions */}
      <p className="mb-4 text-xs font-semibold uppercase tracking-wide text-zinc-400">{t("quickActions")}</p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {tiles.map(({ icon: Icon, color, title, desc, href }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "group flex items-start gap-4 rounded-2xl border border-zinc-200 bg-white p-5 shadow-soft-sm",
              "transition-all duration-200 hover:-translate-y-0.5 hover:border-zinc-300 hover:shadow-soft-md"
            )}
          >
            <div className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-transform duration-200 group-hover:scale-105", color)}>
              <Icon size={22} />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-zinc-950">{title}</p>
              <p className="mt-0.5 text-xs text-zinc-500">{desc}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
