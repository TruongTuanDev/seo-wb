"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Box, Check, ChevronDown, List, ListChecks, LogOut, Plus, PlusSquare, Search, Settings, X } from "lucide-react";
import { CreateStoreModal } from "@/components/dashboard/CreateStoreModal";
import { StoreSettingsModal } from "@/components/dashboard/StoreSettingsModal";
import { PageTransition } from "@/components/ui/PageTransition";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useStore } from "@/contexts/StoreContext";
import { LANGUAGES } from "@/lib/translations";
import { SUPPORT_PHONE } from "@/lib/plans";
import { cn } from "@/lib/utils";

interface StoreItem {
  id: number;
  name: string;
}

export function DashboardClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, logout } = useAuth();
  const { language, setLanguage, t } = useLanguage();
  const { stores, currentStoreId, setCurrentStoreId, addStore, updateStore, removeStore } = useStore();

  const [settingsStore, setSettingsStore] = React.useState<StoreItem | null>(null);
  const [isCreateStoreOpen, setIsCreateStoreOpen] = React.useState(false);
  const [accountOpen, setAccountOpen] = React.useState(false);
  const [langOpen, setLangOpen] = React.useState(false);
  const [storeSearch, setStoreSearch] = React.useState("");
  const accountRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (accountRef.current && !accountRef.current.contains(e.target as Node)) {
        setAccountOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  React.useEffect(() => {
    if (!pathname.startsWith("/finance") && !pathname.startsWith("/cards")) return;
    const queryStoreId = Number(searchParams.get("store_id") || 0);
    if (!queryStoreId) return;
    if (stores.length === 0) return;
    if (stores.some((store) => store.id === queryStoreId) && currentStoreId !== queryStoreId) {
      setCurrentStoreId(queryStoreId);
    }
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("store_id");
    const nextQuery = nextParams.toString();
    router.replace(nextQuery ? `${pathname}?${nextQuery}` : pathname);
  }, [currentStoreId, pathname, router, searchParams, setCurrentStoreId, stores]);

  const activeStore = stores.find((s) => s.id === currentStoreId) ?? stores[0] ?? null;
  const filteredStores = storeSearch.trim()
    ? stores.filter((s) => s.name.toLowerCase().includes(storeSearch.toLowerCase()))
    : stores;

  const productMenuItems = [
    { name: t("list"), href: "/cards", icon: List },
    { name: t("create"), href: "/cards/new", icon: PlusSquare },
  ];

  const switchStore = (storeId: number) => {
    setCurrentStoreId(storeId);
    setAccountOpen(false);
    setStoreSearch("");
    if (pathname.startsWith("/cards")) {
      router.push(pathname.startsWith("/cards/new") ? "/cards/new" : "/cards");
    }
  };

  const onStoreCreated = (newStore: StoreItem) => {
    addStore(newStore);
    setIsCreateStoreOpen(false);
    setAccountOpen(false);
    if (pathname.startsWith("/cards")) {
      router.push("/cards");
    } else if (!pathname.startsWith("/finance") && pathname !== "/" && !pathname.startsWith("/settings")) {
      router.push("/");
    }
  };

  const onStoreSaved = (updatedStore: StoreItem) => {
    updateStore(updatedStore);
  };

  const onStoreDeleted = (deletedStoreId: number) => {
    const fallback = removeStore(deletedStoreId);
    setSettingsStore(null);
    if (!fallback) {
      router.push("/");
    } else if (pathname.startsWith("/cards/new")) {
      router.push("/cards/new");
    } else if (pathname.startsWith("/cards")) {
      router.push("/cards");
    }
    // Finance / dashboard / settings auto-update via context
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#eef2ff_0%,#f8fafc_26%,#f4f4f5_100%)]">
      <header className="fixed inset-x-0 top-0 z-50 border-b border-zinc-200 bg-white/90 shadow-soft-sm backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between px-4 sm:px-6 lg:px-8">

          {/* Left: logo + nav */}
          <div className="flex min-w-0 items-center gap-3 md:gap-7">
            <Link href="/" className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand text-white shadow-soft-md transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98]">
                <Box size={22} />
              </div>
              <span className="hidden truncate text-base font-semibold tracking-tight text-zinc-950 sm:text-lg md:block">
                {t("appName")}
              </span>
            </Link>

            <nav className="hidden items-center gap-1 md:flex">
              {/* Product Cards */}
              <div className="group relative">
                <Link
                  href="/cards"
                  className={cn(
                    "relative inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200 active:scale-[0.98]",
                    pathname.startsWith("/cards")
                      ? "bg-zinc-100 text-zinc-950 before:absolute before:left-0 before:top-1/2 before:h-5 before:w-0.5 before:-translate-y-1/2 before:rounded-full before:bg-brand"
                      : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-950"
                  )}
                >
                  <ListChecks size={17} />
                  {t("productCards")}
                  <ChevronDown size={13} className="transition-transform duration-200 group-hover:rotate-180" />
                </Link>
                <div className="invisible absolute left-0 top-full z-50 mt-2 w-44 translate-y-1 rounded-xl border border-zinc-200 bg-white p-1.5 opacity-0 shadow-soft-xl transition-all duration-200 group-hover:visible group-hover:translate-y-0 group-hover:opacity-100">
                  {productMenuItems.map(({ name, href, icon: Icon }) => (
                    <Link key={name} href={href} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-zinc-700 transition-colors hover:bg-zinc-100 hover:text-zinc-950">
                      <Icon size={15} />{name}
                    </Link>
                  ))}
                </div>
              </div>

            </nav>
          </div>

          {/* Right: combined account dropdown */}
          <div className="flex items-center gap-3">
            <a
              href={`tel:${SUPPORT_PHONE}`}
              className="hidden rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 transition-colors hover:bg-emerald-100 lg:inline-flex"
            >
              Hỗ trợ: {SUPPORT_PHONE}
            </a>
          <div ref={accountRef} className="relative">
            <button
              onClick={() => setAccountOpen((v) => !v)}
              className="flex items-center gap-2.5 rounded-xl border border-zinc-200 bg-white px-3 py-2 shadow-soft-sm transition-all duration-200 hover:border-zinc-300 hover:bg-zinc-50"
            >
              <div className="hidden text-right sm:block">
                <p className="max-w-[150px] truncate text-sm font-semibold text-zinc-900">
                  {activeStore?.name ?? user?.name}
                </p>
                <p className="max-w-[150px] truncate text-xs text-zinc-400">{user?.email}</p>
              </div>
              <ChevronDown
                size={15}
                className={cn("shrink-0 text-zinc-400 transition-transform duration-200", accountOpen && "rotate-180")}
              />
            </button>

            {accountOpen && (
              <div className="absolute right-0 top-full z-50 mt-2 w-80 overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-soft-xl animate-in fade-in slide-in-from-top-2 duration-150">
                {/* Header */}
                <div className="px-5 pt-4 pb-3">
                  <p className="text-base font-semibold text-zinc-950">{t("yourAccount")}</p>
                </div>

                {/* Store search */}
                <div className="px-3 pb-2">
                  <div className="relative">
                    <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                    <input
                      value={storeSearch}
                      onChange={(e) => setStoreSearch(e.target.value)}
                      placeholder={t("searchStores")}
                      className="w-full rounded-lg border border-zinc-200 bg-zinc-50 py-2 pl-8 pr-7 text-sm outline-none placeholder:text-zinc-400 focus:border-zinc-300 focus:bg-white"
                    />
                    {storeSearch && (
                      <button onClick={() => setStoreSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600">
                        <X size={12} />
                      </button>
                    )}
                  </div>
                </div>

                {/* Store list */}
                <div className="max-h-52 overflow-y-auto px-2 pb-1">
                  {filteredStores.length > 0 ? filteredStores.map((store) => {
                    const isActive = store.id === currentStoreId;
                    return (
                      <div key={store.id} className={cn("flex items-center gap-1 rounded-xl px-1 py-1 transition-colors", isActive ? "bg-zinc-50" : "hover:bg-zinc-50")}>
                        <button onClick={() => switchStore(store.id)} className="flex min-w-0 flex-1 items-center gap-3 px-2 py-1.5 text-left">
                          <div className="min-w-0 flex-1">
                            <p className={cn("truncate text-sm font-medium leading-tight", isActive ? "text-zinc-950" : "text-zinc-700")}>
                              {store.name}
                            </p>
                            <p className="text-xs text-zinc-400">ID {store.id}</p>
                          </div>
                          {/* Radio indicator */}
                          <div className={cn(
                            "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 transition-all",
                            isActive ? "border-indigo-600 bg-indigo-600" : "border-zinc-300"
                          )}>
                            {isActive && <div className="h-1.5 w-1.5 rounded-full bg-white" />}
                          </div>
                        </button>
                        <button
                          onClick={() => { setSettingsStore(store); setAccountOpen(false); }}
                          className="rounded-lg p-1.5 text-zinc-300 transition-colors hover:bg-zinc-100 hover:text-zinc-600"
                          title={t("storeSettings")}
                        >
                          <Settings size={13} />
                        </button>
                      </div>
                    );
                  }) : (
                    <p className="py-4 text-center text-sm text-zinc-400">
                      {storeSearch ? "—" : t("noStores")}
                    </p>
                  )}
                </div>

                {/* Add store */}
                <div className="border-t border-zinc-100 px-3 py-2">
                  <button
                    onClick={() => { setIsCreateStoreOpen(true); setAccountOpen(false); }}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-indigo-600 transition-colors hover:bg-indigo-50"
                  >
                    <Plus size={14} />
                    {t("addStore")}
                  </button>
                </div>

                {/* Settings link */}
                <div className="border-t border-zinc-100 px-3 py-2">
                  <Link
                    href="/settings"
                    onClick={() => setAccountOpen(false)}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-zinc-700 transition-colors hover:bg-zinc-100 hover:text-zinc-950"
                  >
                    <Settings size={14} />
                    {t("settings")}
                  </Link>
                </div>

                {/* Language dropdown */}
                <div className="border-t border-zinc-100">
                  <button
                    onClick={() => setLangOpen((v) => !v)}
                    className="flex w-full items-center justify-between px-4 py-3 text-sm transition-colors hover:bg-zinc-50"
                  >
                    <span className="text-xs font-semibold uppercase tracking-wide text-zinc-400">{t("language")}</span>
                    <span className="flex items-center gap-1.5">
                      <span className="text-base leading-none">{LANGUAGES.find((l) => l.code === language)?.flag}</span>
                      <span className="text-sm text-zinc-700">{LANGUAGES.find((l) => l.code === language)?.label}</span>
                      <ChevronDown size={13} className={cn("text-zinc-400 transition-transform duration-200", langOpen && "rotate-180")} />
                    </span>
                  </button>
                  {langOpen && (
                    <div className="pb-2 px-3">
                      {LANGUAGES.map((lang) => (
                        <button
                          key={lang.code}
                          onClick={() => { setLanguage(lang.code); setLangOpen(false); }}
                          className={cn(
                            "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                            language === lang.code
                              ? "bg-indigo-50 font-medium text-indigo-700"
                              : "text-zinc-700 hover:bg-zinc-50 hover:text-zinc-950"
                          )}
                        >
                          <span className="text-base leading-none">{lang.flag}</span>
                          <span className="flex-1 text-left">{lang.label}</span>
                          {language === lang.code && <Check size={14} className="text-indigo-600" />}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Sign out */}
                <div className="border-t border-zinc-100 px-3 pb-3 pt-2">
                  <button
                    onClick={() => logout()}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-rose-600 transition-colors hover:bg-rose-50"
                  >
                    <LogOut size={15} />
                    {t("signOut")}
                  </button>
                </div>
              </div>
            )}
          </div>
          </div>
        </div>

        {/* Mobile nav */}
        <nav className="flex gap-2 overflow-x-auto border-t border-zinc-100 px-4 py-2 md:hidden">
          {productMenuItems.map(({ name, href, icon: Icon }) => (
            <Link
              key={name}
              href={href}
              className={cn(
                "inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150 active:scale-[0.98]",
                pathname.startsWith("/cards") ? "bg-zinc-100 text-zinc-950" : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-950"
              )}
            >
              <Icon size={16} />{name}
            </Link>
          ))}
        </nav>
      </header>

      <main className="pt-20 md:pt-16">
        <div className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8">
          <PageTransition>{children}</PageTransition>
        </div>
      </main>

      <StoreSettingsModal
        store={settingsStore}
        isOpen={Boolean(settingsStore)}
        onClose={() => setSettingsStore(null)}
        onSaved={onStoreSaved}
        onDeleted={onStoreDeleted}
      />

      <CreateStoreModal
        isOpen={isCreateStoreOpen}
        onClose={() => setIsCreateStoreOpen(false)}
        onSuccess={onStoreCreated}
      />
    </div>
  );
}
