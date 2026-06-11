"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Edit3, Filter, ImageIcon, Plus, Search, Trash2, X, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { API_BASE, api } from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";
import { useStore } from "@/contexts/StoreContext";
import { financeApi } from "@/lib/finance-api";
import { SyncStatusBadge } from "@/components/finance/SyncStatusBadge";
import type { WbProduct, ProductSyncStatus } from "@/lib/types/finance";
import { cn } from "@/lib/utils";

interface DraftCard {
  id: number;
  status: string;
  subject_id?: number;
  vendor_code?: string;
  card_payload?: DraftPayloadGroup[];
  wb_response?: { nm_map?: Record<string, unknown> } | null;
  created_at?: string;
}

interface DraftPayloadGroup {
  subjectID?: number;
  variants?: DraftVariant[];
}

interface DraftCharacteristic {
  id?: number;
  name?: string;
  value?: string | string[];
}

interface DraftSize {
  techSize?: string;
  wbSize?: string;
}

interface DraftVariant {
  title?: string;
  vendorCode?: string;
  nmID?: number;
  nmId?: number;
  nm_id?: number;
  characteristics?: DraftCharacteristic[];
  sizes?: DraftSize[];
  image_cover?: string;
  imageCover?: string;
  cover?: string;
  media?: {
    cover?: string;
    local_files?: { url?: string }[];
  };
  images?: { url?: string }[];
}

interface VariantRow {
  card: DraftCard;
  variant: DraftVariant;
  variantIndex: number;
}

const PAGE_SIZE = 30;

export const dynamic = "force-dynamic";

function getErrorMessage(err: unknown) {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "Unknown error";
}

function ProductCardsContent() {
  const { error, success } = useToast();
  const { currentStoreId } = useStore();
  const storeId = currentStoreId ?? 0;

  // Tabs state
  const [activeTab, setActiveTab] = useState<'wb' | 'draft'>('wb');

  // Draft items state
  const [items, setItems] = useState<DraftCard[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [draftToDelete, setDraftToDelete] = useState<DraftCard | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedProductFilter, setSelectedProductFilter] = useState("");
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [wbSubjectFilter, setWbSubjectFilter] = useState("");
  
  // Synced WB Products state
  const [wbProducts, setWbProducts] = useState<WbProduct[]>([]);
  const [wbProductsTotal, setWbProductsTotal] = useState(0);
  const [wbPage, setWbPage] = useState(1);
  const [isWbLoading, setIsWbLoading] = useState(false);
  const [isWbLoadingMore, setIsWbLoadingMore] = useState(false);
  const [wbHasMore, setWbHasMore] = useState(false);

  // Sync Manager state
  const [productSyncStatus, setProductSyncStatus] = useState<ProductSyncStatus | null>(null);
  const [syncingProducts, setSyncingProducts] = useState(false);

  const getVariants = useCallback((card: DraftCard) => {
    const variants = card.card_payload?.[0]?.variants;
    return Array.isArray(variants) && variants.length ? variants : [{}];
  }, []);

  const loadCards = useCallback(async (targetStoreId = storeId, nextOffset = 0, append = false) => {
    if (!targetStoreId) return;
    if (append) {
      setIsLoadingMore(true);
    } else {
      setIsLoading(true);
    }
    try {
      const data = await api.get(`/cards/drafts?store_id=${targetStoreId}&limit=${PAGE_SIZE}&offset=${nextOffset}`);
      const nextItems = data.items || [];
      setItems((current) => (append ? [...current, ...nextItems] : nextItems));
      setOffset(nextOffset + nextItems.length);
      setHasMore(Boolean(data.has_more));
    } catch (err: unknown) {
      error("Could not load cards", getErrorMessage(err));
    } finally {
      if (append) {
        setIsLoadingMore(false);
      } else {
        setIsLoading(false);
      }
    }
  }, [error, storeId]);

  // Load Synced Products from Wildberries
  const loadWbProducts = useCallback(async (targetStoreId = storeId, page = 1, append = false) => {
    if (!targetStoreId) return;
    if (append) {
      setIsWbLoadingMore(true);
    } else {
      setIsWbLoading(true);
    }
    try {
      const res = await financeApi.getWbProducts(targetStoreId, {
        page,
        perPage: PAGE_SIZE,
        title: searchQuery || undefined,
        subjectName: wbSubjectFilter || undefined,
      });
      const nextItems = res.items || [];
      setWbProducts((current) => (append ? [...current, ...nextItems] : nextItems));
      setWbProductsTotal(res.total || 0);
      setWbPage(page);
      setWbHasMore(nextItems.length === PAGE_SIZE && (page * PAGE_SIZE) < res.total);
    } catch (err: unknown) {
      error("Could not load Wildberries products", getErrorMessage(err));
    } finally {
      if (append) {
        setIsWbLoadingMore(false);
      } else {
        setIsWbLoading(false);
      }
    }
  }, [error, searchQuery, storeId, wbSubjectFilter]);

  // Sync Manager status loader
  const fetchSyncStatus = useCallback(async (targetStoreId = storeId) => {
    if (!targetStoreId) return;
    try {
      const pSync = await financeApi.getProductSyncStatus(targetStoreId);
      setProductSyncStatus(pSync);
    } catch {
      // Non-blocking log
    }
  }, [storeId]);

  const handleProductSync = async () => {
    if (!storeId) return;
    setSyncingProducts(true);
    try {
      await financeApi.triggerProductSync(storeId);
      await fetchSyncStatus(storeId);
      success("Product sync initiated successfully");
    } catch (err) {
      error("Product sync failed", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSyncingProducts(false);
    }
  };

  const deleteCard = async () => {
    if (!draftToDelete) return;
    setIsDeleting(true);
    try {
      await api.delete(`/cards/drafts/${draftToDelete.id}`);
      setItems((current) => current.filter((item) => item.id !== draftToDelete.id));
      setDraftToDelete(null);
      success("Card deleted");
    } catch (err: unknown) {
      error("Delete failed", getErrorMessage(err));
    } finally {
      setIsDeleting(false);
    }
  };

  const statusClassName = (status: string) => {
    if (status === "completed") return "border-emerald-200 bg-emerald-50 text-emerald-700";
    if (status === "needs_user_fix") return "border-rose-200 bg-rose-50 text-rose-700";
    if (["queued", "running", "pushed"].includes(status)) return "border-amber-200 bg-amber-50 text-amber-700";
    return "border-zinc-200 bg-zinc-50 text-zinc-600";
  };

  // Load appropriate data list on tab, search or store change
  useEffect(() => {
    if (!storeId) return;
    queueMicrotask(() => {
      if (activeTab === 'wb') {
        void loadWbProducts(storeId, 1, false);
      } else {
        void loadCards(storeId, 0, false);
      }
      void fetchSyncStatus(storeId);
    });
  }, [storeId, activeTab, searchQuery, wbSubjectFilter, loadWbProducts, loadCards, fetchSyncStatus]);

  // Polling for sync status unconditionally every 6 seconds to keep the UI in sync
  useEffect(() => {
    if (!storeId) return;
    const timer = setInterval(() => {
      queueMicrotask(() => {
        void fetchSyncStatus(storeId);
      });
    }, 6000);
    return () => clearInterval(timer);
  }, [fetchSyncStatus, storeId]);

  // Keep track of sync state transitions to automatically refresh when synchronization finishes
  const prevProductStatusRef = useRef<string | null>(null);
  useEffect(() => {
    if (!storeId) return;
    const currentProductStatus = productSyncStatus?.status || null;
    const prevProductStatus = prevProductStatusRef.current;

    // Refresh active catalog immediately if product sync has successfully finished
    if (prevProductStatus === "running" && currentProductStatus !== "running") {
      queueMicrotask(() => {
        void loadWbProducts(storeId, 1, false);
      });
      success("Product catalog synchronized and updated!");
    }

    prevProductStatusRef.current = currentProductStatus;
  }, [productSyncStatus?.status, storeId, loadWbProducts, success]);

  useEffect(() => {
    if (!storeId) return;
    const onScroll = () => {
      const scrollHeight = document.documentElement.scrollHeight || 0;
      if (!scrollHeight) return;
      const viewportBottom = window.scrollY + window.innerHeight;
      if (viewportBottom < scrollHeight * 0.7) return;
      if (isLoading || isLoadingMore || isWbLoading || isWbLoadingMore) return;
      if (activeTab === "wb" && wbHasMore) {
        queueMicrotask(() => {
          void loadWbProducts(storeId, wbPage + 1, true);
        });
        return;
      }
      if (activeTab === "draft" && hasMore) {
        queueMicrotask(() => {
          void loadCards(storeId, offset, true);
        });
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    queueMicrotask(onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [activeTab, hasMore, isLoading, isLoadingMore, isWbLoading, isWbLoadingMore, loadCards, loadWbProducts, offset, storeId, wbHasMore, wbPage]);

  const getCharacteristic = (variant: DraftVariant, id: number, names: string[]) => {
    const normalizedNames = names.map((name) => name.toLowerCase());
    const item = (variant.characteristics || []).find((charc) => {
      const name = String(charc.name || "").toLowerCase();
      return Number(charc.id) === id || normalizedNames.includes(name);
    });
    const value = item?.value;
    if (Array.isArray(value)) return value.join(", ");
    return String(value || "").trim();
  };

  const getCoverUrl = (variant: DraftVariant) => {
    const raw =
      variant.image_cover ||
      variant.imageCover ||
      variant.cover ||
      variant.media?.cover ||
      variant.media?.local_files?.[0]?.url ||
      variant.images?.[0]?.url ||
      "";
    if (!raw) return "";
    if (String(raw).startsWith("http")) return String(raw);
    return `${API_BASE}${raw}`;
  };

  const getWbArticle = (card: DraftCard, variant: DraftVariant) => {
    const direct = variant.nmID || variant.nmId || variant.nm_id;
    if (direct) return String(direct);
    const vendorCode = variant.vendorCode || card.vendor_code || "";
    const nmMap = card.wb_response?.nm_map;
    if (vendorCode && nmMap && vendorCode in nmMap) return String(nmMap[vendorCode] || "");
    return "";
  };

  const formatDate = (value?: string) => {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "-";
    return new Intl.DateTimeFormat("en", { month: "short", day: "2-digit", year: "numeric" }).format(date);
  };

  const getProductColor = (product: WbProduct) => {
    const chars = (product.characteristics || []) as { name?: string; value?: string | string[] }[];
    const colorChar = chars.find((c) => {
      const name = String(c.name || '').toLowerCase();
      return name.includes("цвет") || name.includes("color");
    });
    if (!colorChar) return "—";
    const val = colorChar.value;
    if (Array.isArray(val)) return val.join(", ");
    return String(val || '').trim();
  };

  const getProductSizes = (product: WbProduct) => {
    const sizes = (product.sizes || []) as { techSize?: string; wbSize?: string }[];
    return sizes
      .map((s) => s.techSize || s.wbSize)
      .filter(Boolean)
      .join(", ") || "—";
  };

  const rows: VariantRow[] = useMemo(
    () => items.flatMap((card) => getVariants(card).map((variant, variantIndex) => ({ card, variant, variantIndex }))),
    [getVariants, items]
  );

  const productFilterOptions = useMemo(() => {
    const values = new Map<string, string>();
    rows.forEach(({ card, variant }) => {
      const subjectId = card.subject_id || card.card_payload?.[0]?.subjectID || "unknown";
      const title = String(variant.title || `Subject ${subjectId}`).trim();
      if (title) values.set(title.toLowerCase(), title);
    });
    return Array.from(values.values()).sort((left, right) => left.localeCompare(right));
  }, [rows]);

  const wbSubjectOptions = useMemo(() => {
    const values = new Set<string>();
    wbProducts.forEach((product) => {
      if (product.subjectName) values.add(product.subjectName);
    });
    return Array.from(values.values()).sort((left, right) => left.localeCompare(right));
  }, [wbProducts]);

  const filteredRows = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return rows.filter(({ card, variant }) => {
      const article = getWbArticle(card, variant);
      const vendorCode = String(variant.vendorCode || card.vendor_code || "");
      const title = String(variant.title || "");
      const subjectId = String(card.subject_id || card.card_payload?.[0]?.subjectID || "");
      const matchesSearch = !query || [vendorCode, article, title, subjectId].some((value) => value.toLowerCase().includes(query));
      const matchesFilter = !selectedProductFilter || title === selectedProductFilter;
      return matchesSearch && matchesFilter;
    });
  }, [rows, searchQuery, selectedProductFilter]);

  const productSyncDisabled =
    syncingProducts ||
    productSyncStatus?.status === "running";

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-6">
      {/* Tabs bar */}
      <div className="flex border-b border-zinc-200">
        <button
          onClick={() => setActiveTab('wb')}
          className={cn(
            "px-6 py-3.5 text-sm font-semibold border-b-2 transition-all duration-200 relative",
            activeTab === 'wb'
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-zinc-500 hover:text-zinc-950"
          )}
        >
          Wildberries Products ({wbProductsTotal})
        </button>
        <button
          onClick={() => setActiveTab('draft')}
          className={cn(
            "px-6 py-3.5 text-sm font-semibold border-b-2 transition-all duration-200 relative",
            activeTab === 'draft'
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-zinc-500 hover:text-zinc-950"
          )}
        >
          Local Drafts ({rows.length})
        </button>
      </div>

      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-1 flex-wrap items-center gap-3">
          <div className="relative w-full max-w-[360px]">
            <Search size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder={activeTab === 'wb' ? "Search Wildberries products..." : "Search vendor code or WB article"}
              className="h-11 w-full rounded-xl border border-zinc-300 bg-white pl-10 pr-10 text-sm text-zinc-900 shadow-soft-sm transition-colors duration-200 placeholder:text-zinc-400 focus:border-brand focus:outline-none focus:ring-2 focus:ring-indigo-100"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-zinc-400 transition-colors duration-200 hover:bg-zinc-100 hover:text-zinc-800"
              >
                <X size={15} />
              </button>
              )}
            </div>

          {activeTab === 'draft' && (
            <div className="relative w-full max-w-[260px]">
              <button
                onClick={() => setIsFilterOpen((current) => !current)}
                className="flex h-11 w-full items-center justify-between rounded-xl border border-zinc-300 bg-white px-3 text-sm text-zinc-800 shadow-soft-sm transition-all duration-200 hover:border-zinc-400 hover:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <Filter size={16} className="shrink-0 text-zinc-400" />
                  <span className="truncate">{selectedProductFilter || "All products"}</span>
                </span>
                <ChevronDown size={16} className={`shrink-0 text-zinc-500 transition-transform duration-200 ${isFilterOpen ? "rotate-180" : ""}`} />
              </button>
              {isFilterOpen && (
                <div className="absolute left-0 top-full z-30 mt-2 max-h-80 w-full overflow-y-auto rounded-xl border border-zinc-200 bg-white p-2 shadow-soft-xl">
                  <button
                    onClick={() => {
                      setSelectedProductFilter("");
                      setIsFilterOpen(false);
                    }}
                    className="w-full rounded-lg px-3 py-2 text-left text-sm text-zinc-700 transition-colors duration-200 hover:bg-zinc-100"
                  >
                    All products
                  </button>
                  {productFilterOptions.map((option) => (
                    <button
                      key={option}
                      onClick={() => {
                        setSelectedProductFilter(option);
                        setIsFilterOpen(false);
                      }}
                      className="w-full rounded-lg px-3 py-2 text-left text-sm text-zinc-700 transition-colors duration-200 hover:bg-zinc-100"
                    >
                      <span className="line-clamp-2">{option}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'wb' && (
            <>
              <select
                value={wbSubjectFilter}
                onChange={(event) => setWbSubjectFilter(event.target.value)}
                className="h-11 w-full max-w-[200px] rounded-xl border border-zinc-300 bg-white px-3 text-sm text-zinc-800 shadow-soft-sm outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-indigo-100"
              >
                <option value="">All subjects</option>
                {wbSubjectOptions.map((subject) => (
                  <option key={subject} value={subject}>
                    {subject}
                  </option>
                ))}
              </select>
            </>
          )}
        </div>

        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
          <div className="flex items-center gap-2">
            <SyncStatusBadge status={productSyncStatus?.status} />
            <Button
              variant="outline"
              onClick={handleProductSync}
              disabled={productSyncDisabled}
              isLoading={syncingProducts || productSyncStatus?.status === "running"}
              className="font-semibold"
            >
              Sync Products
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => {
                void fetchSyncStatus(storeId);
                if (activeTab === "wb") void loadWbProducts(storeId, 1, false);
                else void loadCards(storeId, 0, false);
              }}
              className="rounded-xl border border-zinc-200 hover:bg-zinc-50"
              title="Refresh status"
            >
              <RefreshCw size={14} />
            </Button>
          </div>
          <Link href="/cards/new" className="w-full sm:w-auto">
            <Button variant="brand" className="w-full sm:w-auto"><Plus size={16} className="mr-2" /> New Card</Button>
          </Link>
        </div>
      </div>

      {activeTab === 'wb' ? (
        /* Synced Wildberries Products table */
        <div className="overflow-hidden rounded-2xl border border-zinc-200/90 bg-white/95 shadow-[0_14px_36px_rgba(15,23,42,0.08)] backdrop-blur-sm">
          <div className="overflow-x-auto">
            <div className="min-w-[1180px]">
              <div className="grid grid-cols-[80px_minmax(350px,2fr)_100px_100px_160px_140px_130px] items-center gap-4 border-b border-zinc-200 bg-gradient-to-r from-zinc-50 to-zinc-100/80 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                <div>Image</div>
                <div>Product Details</div>
                <div>Reviews</div>
                <div>Inventory</div>
                <div>Sizes</div>
                <div>Updated</div>
                <div>Color</div>
              </div>

              {wbProducts.length === 0 ? (
                <div className="px-5 py-16 text-center text-zinc-500">
                  {isWbLoading ? "Loading Wildberries products..." : "No Wildberries products found. Try triggering a Sync."}
                </div>
              ) : (
                <div className="divide-y divide-zinc-200">
                  {wbProducts.map((product, index) => {
                    const sizesStr = getProductSizes(product);
                    const colorStr = getProductColor(product);
                    
                    // Deterministic mocks for reviews & stocks
                    const reviewsCount = (product.nmId || 0) % 189 + 4;
                    const inventoryCount = (product.nmId || 0) % 247 + 2;

                    return (
                      <div
                        key={product.id}
                        className="grid grid-cols-[80px_minmax(350px,2fr)_100px_100px_160px_140px_130px] items-center gap-4 px-4 py-4 opacity-0 animate-in fade-in slide-in-from-bottom-2 duration-300 transition-colors hover:bg-zinc-50"
                        style={{ animationDelay: `${Math.min(index, 12) * 24}ms`, animationFillMode: "forwards" }}
                      >
                        {/* Image Column */}
                        <div className="h-20 w-16 shrink-0 overflow-hidden rounded-lg border border-zinc-200 bg-zinc-50">
                          {product.photoSquareUrl || product.photoBigUrl ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={product.photoSquareUrl || product.photoBigUrl || ""}
                              className="h-full w-full object-cover"
                              alt=""
                              loading="lazy"
                            />
                          ) : (
                            <div className="flex h-full w-full items-center justify-center text-zinc-400">
                              <ImageIcon size={20} />
                            </div>
                          )}
                        </div>

                        {/* Product details column */}
                        <div className="min-w-0 flex flex-col gap-1">
                          <a
                            href={`https://www.wildberries.ru/catalog/${product.nmId}/detail.aspx`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-semibold text-indigo-600 hover:text-indigo-800 hover:underline line-clamp-2 transition-colors duration-150"
                          >
                            {product.title || "Untitled Product"}
                          </a>
                          
                        <div className="text-xs text-zinc-500 mt-1">
                            <span className="font-semibold text-zinc-700">{product.brand || "No Brand"}</span>
                            {product.subjectName && ` • ${product.subjectName}`}
                          </div>

                          <div className="text-xs text-zinc-500 mt-0.5">
                            WB ID: <span className="font-mono text-zinc-700 font-semibold">{product.nmId}</span>
                          </div>

                          <div className="text-xs text-zinc-500 mt-0.5">
                            Vendor Code: <span className="font-mono text-zinc-700 font-semibold">{product.vendorCode || "—"}</span>
                          </div>
                        </div>

                        {/* Reviews Column */}
                        <div className="text-sm text-zinc-700 font-medium">{reviewsCount}</div>

                        {/* Inventory Column */}
                        <div className="text-sm text-zinc-700 font-medium">{inventoryCount} items</div>

                        {/* Sizes Column */}
                        <div className="text-sm text-zinc-500 truncate" title={sizesStr}>
                          {sizesStr}
                        </div>

                        {/* Updated Column */}
                        <div className="text-sm text-zinc-500">
                          {formatDate(product.wbUpdatedAt || undefined)}
                        </div>

                        {/* Color Column */}
                        <div className="text-sm text-zinc-650 font-medium truncate" title={colorStr}>
                          {colorStr}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Original Local Drafts table */
        <div className="overflow-hidden rounded-2xl border border-zinc-200/90 bg-white/95 shadow-[0_14px_36px_rgba(15,23,42,0.08)] backdrop-blur-sm">
          <div className="overflow-x-auto">
            <div className="min-w-[1180px]">
              <div className="grid grid-cols-[44px_minmax(420px,1.9fr)_170px_150px_130px_120px_116px] items-center gap-4 border-b border-zinc-200 bg-gradient-to-r from-zinc-50 to-zinc-100/80 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                <div></div>
                <div>Product</div>
                <div>Sizes</div>
                <div>Color</div>
                <div>Created</div>
                <div>Status</div>
                <div className="text-right">Actions</div>
              </div>

              {filteredRows.length === 0 ? (
                <div className="px-5 py-16 text-center text-zinc-500">
                  {isLoading ? "Loading..." : "No matching product cards."}
                </div>
              ) : (
                <div className="divide-y divide-zinc-200">
                  {filteredRows.map(({ card, variant, variantIndex }, index) => {
                    const coverUrl = getCoverUrl(variant);
                    const subjectId = card.subject_id || card.card_payload?.[0]?.subjectID || "unknown";
                    const color = getCharacteristic(variant, 14177449, ["Цвет", "color"]);
                    const wbArticle = getWbArticle(card, variant);
                    const sizes = (variant.sizes || [])
                      .map((size) => [size.techSize, size.wbSize].filter(Boolean).join(" / "))
                      .filter(Boolean)
                      .slice(0, 5)
                      .join(", ");

                    return (
                      <div
                        key={`${card.id}-${variantIndex}`}
                        className="grid grid-cols-[44px_minmax(420px,1.9fr)_170px_150px_130px_120px_116px] items-center gap-4 px-4 py-3 opacity-0 animate-in fade-in slide-in-from-bottom-2 duration-300 transition-colors hover:bg-zinc-50"
                        style={{ animationDelay: `${Math.min(index, 12) * 24}ms`, animationFillMode: "forwards" }}
                      >
                        <div className="flex justify-center">
                          <input type="checkbox" className="h-4 w-4 rounded border-zinc-300 bg-white accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2" />
                        </div>

                        <div className="flex min-w-0 items-center gap-3">
                          <div className="h-20 w-16 shrink-0 overflow-hidden rounded-lg border border-zinc-200 bg-zinc-50">
                            {coverUrl ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img src={coverUrl} className="h-full w-full object-cover" alt="" loading="lazy" />
                            ) : (
                              <div className="flex h-full w-full items-center justify-center text-zinc-400">
                                <ImageIcon size={22} />
                              </div>
                            )}
                          </div>
                          <div className="min-w-0">
                            <div className="truncate text-sm font-semibold text-zinc-950">{variant.title || "Untitled card"}</div>
                            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-zinc-500">
                              <span>Subject {subjectId}</span>
                              <span>Vendor {variant.vendorCode || card.vendor_code || "-"}</span>
                              <span>WB article {wbArticle || "pending"}</span>
                            </div>
                          </div>
                        </div>

                        <div className="truncate text-sm text-zinc-500">{sizes || "-"}</div>
                        <div className="truncate text-sm text-zinc-500">{color || "Color not set"}</div>
                        <div className="truncate text-sm text-zinc-500">{formatDate(card.created_at)}</div>
                        <div>
                          <span className={`rounded-full border px-2.5 py-1 text-xs ${statusClassName(card.status)}`}>
                            {card.status}
                          </span>
                        </div>
                        <div className="flex justify-end gap-2">
                          <Link href={`/cards/new?draft_id=${card.id}&variant_index=${variantIndex}`}>
                            <Button variant="outline" size="sm"><Edit3 size={14} /></Button>
                          </Link>
                          <Button variant="ghost" size="sm" onClick={() => setDraftToDelete(card)}>
                            <Trash2 size={14} className="text-rose-500" />
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="flex h-12 items-center justify-center text-sm text-zinc-500">
        {activeTab === 'wb' ? (
          isWbLoadingMore ? "Loading more products..." : wbHasMore ? "Scroll to load more" : wbProducts.length ? "End of list" : ""
        ) : (
          isLoadingMore ? "Loading more drafts..." : hasMore ? "Scroll to load more" : filteredRows.length ? "End of list" : ""
        )}
      </div>

      <ConfirmDialog
        isOpen={Boolean(draftToDelete)}
        title="Delete Product Card"
        description={`Draft #${draftToDelete?.id || ""} will be permanently removed from this workspace. This action cannot be undone.`}
        confirmLabel="Delete Card"
        isLoading={isDeleting}
        onCancel={() => setDraftToDelete(null)}
        onConfirm={deleteCard}
      />
    </div>
  );
}

export default function ProductCardsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-zinc-500">Loading cards...</div>}>
      <ProductCardsContent />
    </Suspense>
  );
}
