"use client";

import { useCallback, useEffect, useState } from "react";
import { ImagePlus, Trash2, UserRound, UsersRound } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Modal } from "@/components/ui/Modal";
import { api, publicAssetUrl } from "@/lib/api";
import { fetchShopModels, type ShopModel } from "@/lib/shopModels";
import { useStore } from "@/contexts/StoreContext";
import { useToast } from "@/contexts/ToastContext";

const EMPTY_FORM = {
  name: "",
};

export default function ShopModelsPage() {
  const { currentStoreId, stores } = useStore();
  const { success, error } = useToast();
  const [models, setModels] = useState<ShopModel[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [image, setImage] = useState<File | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ShopModel | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const activeStore = stores.find((store) => store.id === currentStoreId);

  const loadModels = useCallback(async () => {
    if (!currentStoreId) return;
    setIsLoading(true);
    try {
      setModels(await fetchShopModels(currentStoreId));
    } catch (requestError) {
      error("Không thể tải My Models", messageFrom(requestError));
    } finally {
      setIsLoading(false);
    }
  }, [currentStoreId, error]);

  useEffect(() => {
    queueMicrotask(() => void loadModels());
  }, [loadModels]);

  const createModel = async () => {
    if (!currentStoreId || !image || form.name.trim().length < 2) {
      error("Thiếu thông tin", "Hãy nhập tên và chọn một ảnh người mẫu.");
      return;
    }
    setIsSaving(true);
    try {
      const data = new FormData();
      data.append("store_id", String(currentStoreId));
      data.append("reference_image", image);
      data.append("metadata_json", JSON.stringify({
        name: form.name.trim(),
      }));
      await api.post("/shop-models", data);
      success("Đã thêm model cho shop", "Model này chỉ hiển thị trong shop hiện tại.");
      setForm(EMPTY_FORM);
      setImage(null);
      setIsOpen(false);
      await loadModels();
    } catch (requestError) {
      error("Không thể lưu model", messageFrom(requestError));
    } finally {
      setIsSaving(false);
    }
  };

  const deleteModel = async () => {
    if (!currentStoreId || !deleteTarget) return;
    setIsDeleting(true);
    try {
      await api.delete(`/shop-models/${deleteTarget.id}?store_id=${currentStoreId}`);
      setModels((current) => current.filter((item) => item.id !== deleteTarget.id));
      setDeleteTarget(null);
      success("Đã xóa model");
    } catch (requestError) {
      error("Không thể xóa model", messageFrom(requestError));
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-6xl space-y-7">
      <section className="overflow-hidden rounded-3xl border border-sky-200 bg-[radial-gradient(circle_at_top_right,#cffafe_0,transparent_36%),linear-gradient(135deg,#f8fafc,#eff6ff)] p-7 shadow-soft-md">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">
              <UsersRound size={14} /> Model riêng theo shop
            </div>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-zinc-950">My Models</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-600">
              Thư viện người mẫu của <strong>{activeStore?.name || "shop hiện tại"}</strong>. Model ở đây không xuất hiện trong bất kỳ shop nào khác.
            </p>
          </div>
          <Button variant="brand" className="h-11" onClick={() => setIsOpen(true)}>
            <ImagePlus size={17} className="mr-2" /> Tải model lên
          </Button>
        </div>
      </section>

      {isLoading ? (
        <div className="rounded-2xl border border-zinc-200 bg-white py-16 text-center text-sm text-zinc-500">Đang tải model...</div>
      ) : models.length === 0 ? (
        <button onClick={() => setIsOpen(true)} className="flex w-full flex-col items-center rounded-2xl border border-dashed border-zinc-300 bg-white px-6 py-16 text-center transition hover:border-sky-400 hover:bg-sky-50/40">
          <UserRound size={34} className="text-sky-600" />
          <span className="mt-4 text-base font-semibold text-zinc-900">Shop chưa có model riêng</span>
          <span className="mt-1 text-sm text-zinc-500">Tải ảnh người mẫu thật để dùng nhất quán cho các lần tạo ảnh.</span>
        </button>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {models.map((model) => (
            <article key={model.id} className="group overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-soft-sm">
              <div className="aspect-[3/4] overflow-hidden bg-zinc-100">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={modelUrl(model.frontImageUrl)} alt={model.name} className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]" />
              </div>
              <div className="flex items-start justify-between gap-3 p-4">
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-semibold text-zinc-950">{model.name}</h2>
                  <p className="mt-1 text-xs text-zinc-500">Model riêng của shop</p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(model)} title="Xóa model">
                  <Trash2 size={15} className="text-rose-500" />
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}

      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title="Thêm model cho shop" description="Ảnh nên rõ toàn thân, chính diện, ánh sáng đều và không bị che khuất.">
        <div className="space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-zinc-800">Tên model</span>
            <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Ví dụ: Anna 01" className="h-11 w-full rounded-xl border border-zinc-300 px-3 outline-none focus:border-brand focus:ring-2 focus:ring-indigo-100" />
          </label>
          <label className="flex cursor-pointer flex-col items-center rounded-2xl border border-dashed border-zinc-300 bg-zinc-50 px-4 py-8 text-center hover:border-sky-400 hover:bg-sky-50">
            <ImagePlus size={26} className="text-sky-600" />
            <span className="mt-2 text-sm font-semibold text-zinc-800">{image?.name || "Chọn ảnh model từ máy"}</span>
            <span className="mt-1 text-xs text-zinc-500">JPG, PNG hoặc WEBP, tối đa 10 MB</span>
            <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(event) => setImage(event.target.files?.[0] || null)} />
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setIsOpen(false)}>Hủy</Button>
            <Button variant="brand" isLoading={isSaving} onClick={() => void createModel()}>Lưu vào My Models</Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog isOpen={Boolean(deleteTarget)} title="Xóa model?" description={`${deleteTarget?.name || "Model"} sẽ bị xóa khỏi shop hiện tại.`} confirmLabel="Xóa model" isLoading={isDeleting} onCancel={() => setDeleteTarget(null)} onConfirm={deleteModel} />
    </div>
  );
}

function modelUrl(url: string) {
  return publicAssetUrl(url);
}

function messageFrom(value: unknown) {
  return value instanceof Error ? value.message : "Đã xảy ra lỗi.";
}
