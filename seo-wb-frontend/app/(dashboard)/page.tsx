"use client";

import React, { useEffect, useState } from "react";
import { ListChecks, Plus, Settings, Store, Sparkles, UsersRound } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { CreateStoreModal } from "@/components/dashboard/CreateStoreModal";
import { Spinner } from "@/components/ui/Spinner";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useStore } from "@/contexts/StoreContext";
import { api } from "@/lib/api";
import { PLAN_OPTIONS, SUPPORT_PHONE, planLabel } from "@/lib/plans";
import { cn } from "@/lib/utils";

type UsageSummary = {
  plan_type: string;
  monthly_quota: number;
  used_quota: number;
  remaining_quota: number;
  quota_percent: number;
  max_images_per_job: number;
  allow_gpt_image: boolean;
  priority_queue: boolean;
  credit_balance: number;
  credits_used: number;
  credits_granted: number;
  remaining_cards: number;
  remaining_images: number;
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
      icon: UsersRound,
      color: "bg-sky-50 text-sky-600",
      title: "My Models",
      desc: "Quản lý người mẫu riêng của shop",
      href: "/models",
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
    <div className="mx-auto max-w-4xl">
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
          <section className="mt-4 rounded-3xl border border-zinc-200 bg-white p-5 shadow-soft-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-400">Số dư hiện tại</p>
                <h2 className="mt-1 text-lg font-semibold text-zinc-950">Plan {planLabel(usage.plan_type)}</h2>
              </div>
              <div className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-semibold text-emerald-700">
                {usage.remaining_cards} thẻ · {usage.remaining_images} ảnh
              </div>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Thẻ còn lại</p>
                <p className="mt-1 text-3xl font-bold text-emerald-950">{usage.remaining_cards}</p>
                <p className="mt-1 text-xs text-emerald-700">Đã tạo {usage.used_quota} / tổng {usage.monthly_quota} thẻ</p>
              </div>
              <div className="rounded-2xl border border-sky-100 bg-sky-50 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">Ảnh còn lại</p>
                <p className="mt-1 text-3xl font-bold text-sky-950">{usage.remaining_images}</p>
                <p className="mt-1 text-xs text-sky-700">Đã dùng {usage.credits_used} / đã cấp {usage.credits_granted} ảnh</p>
              </div>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-zinc-200">
              <div className="h-full rounded-full bg-brand" style={{ width: `${Math.min(100, usage.quota_percent)}%` }} />
            </div>
            <p className="mt-3 text-xs text-zinc-500">
              Max/job: {usage.max_images_per_job} · GPT image: {usage.allow_gpt_image ? "enabled" : "disabled"} · Priority: {usage.priority_queue ? "yes" : "no"}
            </p>
            <p className="mt-1 text-xs text-zinc-500">
              Next reset: {usage.quota_reset_at ? new Date(usage.quota_reset_at).toLocaleDateString() : "Not scheduled"}
            </p>
            {(usage.remaining_cards <= 0 || usage.remaining_images <= 0) && (
              <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                Bạn đã hết {usage.remaining_cards <= 0 ? "thẻ" : "ảnh"}. Liên hệ {SUPPORT_PHONE} để nạp thêm.
              </div>
            )}
          </section>
        )}
      </div>

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

      <section className="mt-8 rounded-[28px] border border-zinc-200 bg-white/95 p-5 shadow-soft-sm">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-600">Gói sử dụng</p>
            <h2 className="mt-2 text-xl font-semibold text-zinc-950">Nạp thêm thẻ và ảnh AI cho shop</h2>
            <p className="mt-1 text-sm text-zinc-500">Liên hệ hỗ trợ: <span className="font-semibold text-zinc-900">{SUPPORT_PHONE}</span></p>
          </div>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-4">
          {PLAN_OPTIONS.map((plan) => (
            <article key={plan.value} className="rounded-2xl border border-zinc-200 bg-gradient-to-b from-white to-zinc-50 p-4">
              <div className="text-sm font-semibold text-zinc-950">{plan.label}</div>
              <div className="mt-2 text-2xl font-bold text-zinc-950">{plan.priceRub.toLocaleString("ru-RU")} ₽</div>
              <div className="mt-3 space-y-1 text-sm text-zinc-600">
                <p>{plan.cards} thẻ tạo bài</p>
                <p>{plan.images} ảnh AI</p>
              </div>
              <p className="mt-3 text-xs text-zinc-500">{plan.description}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
