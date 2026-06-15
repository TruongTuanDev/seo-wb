"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight, Edit3, ImageIcon, Plus, Search, Sparkles, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { API_BASE, api } from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";
import { useStore } from "@/contexts/StoreContext";

interface DraftCharacteristic {
  id?: number;
  name?: string;
  value?: string | string[];
}

interface DraftVariant {
  title?: string;
  vendorCode?: string;
  nmID?: number;
  characteristics?: DraftCharacteristic[];
  sizes?: { techSize?: string; wbSize?: string }[];
  media?: {
    cover?: string;
    local_files?: { url?: string }[];
  };
}

interface DraftCard {
  id: number;
  status: string;
  subject_id?: number;
  vendor_code?: string;
  card_payload?: { subjectID?: number; variants?: DraftVariant[] }[];
  wb_response?: { nm_map?: Record<string, unknown>; source_nm_id?: number } | null;
  created_at?: string;
}

interface VariantRow {
  card: DraftCard;
  variant: DraftVariant;
  variantIndex: number;
}

const PAGE_SIZE = 30;
const SHOW_WB_IMPORT = false;

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Request failed";
}

export default function ProductCardsPage() {
  const router = useRouter();
  const { currentStoreId } = useStore();
  const { error, success } = useToast();
  const storeId = currentStoreId ?? 0;
  const [items, setItems] = useState<DraftCard[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [search, setSearch] = useState("");
  const [nmId, setNmId] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  const [draftToDelete, setDraftToDelete] = useState<DraftCard | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const loadCards = useCallback(async (nextOffset = 0, append = false) => {
    if (!storeId) return;
    if (append) {
      setIsLoadingMore(true);
    } else {
      setIsLoading(true);
    }
    try {
      const response = await api.get(`/cards/drafts?store_id=${storeId}&limit=${PAGE_SIZE}&offset=${nextOffset}`);
      const nextItems = response.items || [];
      setItems((current) => append ? [...current, ...nextItems] : nextItems);
      setOffset(nextOffset + nextItems.length);
      setHasMore(Boolean(response.has_more));
    } catch (requestError) {
      error("Không thể tải lịch sử thẻ", getErrorMessage(requestError));
    } finally {
      if (append) {
        setIsLoadingMore(false);
      } else {
        setIsLoading(false);
      }
    }
  }, [error, storeId]);

  useEffect(() => {
    queueMicrotask(() => void loadCards());
  }, [loadCards]);

  const rows = useMemo<VariantRow[]>(
    () => items.flatMap((card) => {
      const variants = card.card_payload?.[0]?.variants || [{}];
      return variants.map((variant, variantIndex) => ({ card, variant, variantIndex }));
    }),
    [items],
  );

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return rows;
    return rows.filter(({ card, variant }) => {
      const values = [
        variant.title,
        variant.vendorCode,
        card.vendor_code,
        getNmId(card, variant),
        card.subject_id,
      ];
      return values.some((value) => String(value || "").toLowerCase().includes(query));
    });
  }, [rows, search]);

  const importProduct = async () => {
    const parsedNmId = Number(nmId.trim());
    if (!Number.isInteger(parsedNmId) || parsedNmId <= 0) {
      error("WB ID không hợp lệ", "Hãy nhập NM ID dạng số, ví dụ 1152698127.");
      return;
    }
    if (!storeId) {
      error("Chưa chọn cửa hàng", "Hãy chọn cửa hàng Wildberries trước.");
      return;
    }
    setIsImporting(true);
    try {
      const draft = await api.post(`/cards/import-wb?store_id=${storeId}`, { nm_id: parsedNmId });
      success("Đã tải sản phẩm từ WB", "Đang mở nội dung để tối ưu SEO.");
      router.push(`/cards/new?draft_id=${draft.id}`);
    } catch (requestError) {
      error("Không thể tải sản phẩm", getErrorMessage(requestError));
    } finally {
      setIsImporting(false);
    }
  };

  const deleteCard = async () => {
    if (!draftToDelete) return;
    setIsDeleting(true);
    try {
      await api.delete(`/cards/drafts/${draftToDelete.id}`);
      setItems((current) => current.filter((item) => item.id !== draftToDelete.id));
      setDraftToDelete(null);
      success("Đã xóa thẻ");
    } catch (requestError) {
      error("Xóa thất bại", getErrorMessage(requestError));
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-6">
      {SHOW_WB_IMPORT && (
        <section className="relative overflow-hidden rounded-3xl border border-emerald-200/80 bg-[linear-gradient(125deg,#f0fdf4_0%,#ffffff_48%,#ecfeff_100%)] p-6 shadow-[0_20px_60px_rgba(15,118,110,0.10)] sm:p-8">
          <div className="absolute -right-16 -top-20 h-52 w-52 rounded-full bg-emerald-200/30 blur-3xl" />
          <div className="relative grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(420px,0.9fr)] lg:items-end">
            <div>
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700">
                <Sparkles size={13} />
                SEO cho sản phẩm đang bán
              </div>
              <h1 className="max-w-2xl text-3xl font-semibold tracking-tight text-zinc-950 sm:text-4xl">
                Nhập đúng sản phẩm cần tối ưu, không đồng bộ cả cửa hàng
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-600 sm:text-base">
                Nhập NM ID trên Wildberries. Hệ thống sẽ tải tiêu đề, mô tả, thuộc tính và ảnh hiện tại thành một bản nháp để bạn tối ưu SEO.
              </p>
            </div>

            <div className="rounded-2xl border border-white bg-white/90 p-3 shadow-soft-md backdrop-blur">
              <label className="mb-2 block px-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                WB NM ID
              </label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  inputMode="numeric"
                  value={nmId}
                  onChange={(event) => setNmId(event.target.value.replace(/\D/g, ""))}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void importProduct();
                  }}
                  placeholder="Ví dụ: 1152698127"
                  className="h-12 min-w-0 flex-1 rounded-xl border border-zinc-300 bg-white px-4 font-mono text-base text-zinc-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
                />
                <Button
                  variant="brand"
                  className="h-12 whitespace-nowrap bg-emerald-700 px-5 hover:bg-emerald-800"
                  isLoading={isImporting}
                  onClick={() => void importProduct()}
                >
                  Tải về & tối ưu SEO
                  <ArrowRight size={16} className="ml-2" />
                </Button>
              </div>
            </div>
          </div>
        </section>
      )}

      <section className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-400">Lịch sử làm việc</p>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight text-zinc-950">Các thẻ sản phẩm đã tạo</h2>
          </div>
          <div className="flex w-full gap-2 sm:w-auto">
            <div className="relative min-w-0 flex-1 sm:w-80">
              <Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Tìm tên, vendor code hoặc WB ID"
                className="h-11 w-full rounded-xl border border-zinc-300 bg-white pl-10 pr-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-indigo-100"
              />
            </div>
            <Link href="/cards/new">
              <Button variant="brand" className="h-11">
                <Plus size={16} className="mr-2" />
                Tạo thẻ mới
              </Button>
            </Link>
          </div>
        </div>

        <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-[0_14px_36px_rgba(15,23,42,0.07)]">
          <div className="grid min-w-[920px] grid-cols-[76px_minmax(340px,1.8fr)_150px_150px_120px_110px] gap-4 border-b border-zinc-200 bg-zinc-50 px-5 py-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">
            <div>Ảnh</div>
            <div>Sản phẩm</div>
            <div>Màu</div>
            <div>Ngày tạo</div>
            <div>Trạng thái</div>
            <div className="text-right">Thao tác</div>
          </div>
          <div className="min-w-[920px] divide-y divide-zinc-200">
            {filteredRows.length === 0 ? (
              <div className="px-5 py-16 text-center text-sm text-zinc-500">
                {isLoading ? "Đang tải lịch sử..." : "Chưa có thẻ sản phẩm phù hợp."}
              </div>
            ) : filteredRows.map(({ card, variant, variantIndex }) => {
              const cover = getCoverUrl(variant);
              const color = getCharacteristic(variant, 14177449, ["Цвет", "color"]);
              const productNmId = getNmId(card, variant);
              return (
                <div key={`${card.id}-${variantIndex}`} className="grid grid-cols-[76px_minmax(340px,1.8fr)_150px_150px_120px_110px] items-center gap-4 px-5 py-4 transition hover:bg-zinc-50/80">
                  <div className="h-20 w-16 overflow-hidden rounded-xl border border-zinc-200 bg-zinc-100">
                    {cover ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={cover} alt="" className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full items-center justify-center text-zinc-400"><ImageIcon size={21} /></div>
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-zinc-950">{variant.title || "Thẻ chưa có tiêu đề"}</p>
                    <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-zinc-500">
                      <span>Vendor: {variant.vendorCode || card.vendor_code || "-"}</span>
                      <span>WB ID: {productNmId || "chưa đăng"}</span>
                    </div>
                  </div>
                  <div className="truncate text-sm text-zinc-600">{color || "Chưa đặt"}</div>
                  <div className="text-sm text-zinc-500">{formatDate(card.created_at)}</div>
                  <div>
                    <span className={`rounded-full border px-2.5 py-1 text-xs ${statusClassName(card.status)}`}>{statusLabel(card.status)}</span>
                  </div>
                  <div className="flex justify-end gap-2">
                    <Link href={`/cards/new?draft_id=${card.id}&variant_index=${variantIndex}`}>
                      <Button variant="outline" size="sm" title="Chỉnh sửa và tối ưu SEO"><Edit3 size={14} /></Button>
                    </Link>
                    <Button variant="ghost" size="sm" onClick={() => setDraftToDelete(card)} title="Xóa khỏi lịch sử">
                      <Trash2 size={14} className="text-rose-500" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {hasMore && (
          <div className="flex justify-center">
            <Button variant="outline" isLoading={isLoadingMore} onClick={() => void loadCards(offset, true)}>
              Tải thêm lịch sử
            </Button>
          </div>
        )}
      </section>

      <ConfirmDialog
        isOpen={Boolean(draftToDelete)}
        title="Xóa thẻ khỏi lịch sử"
        description={`Thẻ #${draftToDelete?.id || ""} sẽ bị xóa vĩnh viễn khỏi hệ thống.`}
        confirmLabel="Xóa thẻ"
        isLoading={isDeleting}
        onCancel={() => setDraftToDelete(null)}
        onConfirm={deleteCard}
      />
    </div>
  );
}

function getCharacteristic(variant: DraftVariant, id: number, names: string[]) {
  const normalizedNames = names.map((name) => name.toLowerCase());
  const item = (variant.characteristics || []).find((characteristic) => (
    Number(characteristic.id) === id || normalizedNames.includes(String(characteristic.name || "").toLowerCase())
  ));
  return Array.isArray(item?.value) ? item.value.join(", ") : String(item?.value || "").trim();
}

function getCoverUrl(variant: DraftVariant) {
  const raw = variant.media?.cover || variant.media?.local_files?.[0]?.url || "";
  if (!raw) return "";
  return raw.startsWith("http") ? raw : `${API_BASE}${raw}`;
}

function getNmId(card: DraftCard, variant: DraftVariant) {
  if (variant.nmID) return String(variant.nmID);
  if (card.wb_response?.source_nm_id) return String(card.wb_response.source_nm_id);
  const code = variant.vendorCode || card.vendor_code || "";
  return String(card.wb_response?.nm_map?.[code] || "");
}

function formatDate(value?: string) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "-"
    : new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }).format(date);
}

function statusClassName(status: string) {
  if (status === "completed") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (status === "imported") return "border-cyan-200 bg-cyan-50 text-cyan-700";
  if (status === "needs_user_fix") return "border-rose-200 bg-rose-50 text-rose-700";
  if (["queued", "running", "pushed"].includes(status)) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-zinc-200 bg-zinc-50 text-zinc-600";
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: "Bản nháp",
    imported: "Đã nhập WB",
    completed: "Hoàn thành",
    needs_user_fix: "Cần kiểm tra",
    queued: "Đang chờ",
    running: "Đang xử lý",
    pushed: "Đã gửi WB",
  };
  return labels[status] || status;
}
