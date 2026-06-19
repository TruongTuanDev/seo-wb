"use client";

import React, { useCallback, useEffect, useState } from "react";
import { FolderSync, Lock, Plus, RefreshCw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { CategorySelector } from "@/components/cards/CategorySelector";
import { useStore } from "@/contexts/StoreContext";
import { useToast } from "@/contexts/ToastContext";
import { api } from "@/lib/api";

interface TnvedOption {
  code: string;
  count: number;
}

interface StoreCategory {
  id: number;
  subject_id: number;
  subject_name: string | null;
  tnved: string | null;
  tnved_options: TnvedOption[];
  source: string;
  locked: boolean;
  product_count: number;
  last_synced_at: string | null;
}

function getErrorMessage(err: unknown) {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "Unknown error";
}

export default function ShopCategoriesPage() {
  const { currentStoreId } = useStore();
  const { success, error } = useToast();

  const [categories, setCategories] = useState<StoreCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [progress, setProgress] = useState<{ total_scanned: number; categories_found: number } | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<StoreCategory | null>(null);

  const load = useCallback(() => {
    if (!currentStoreId) return;
    setLoading(true);
    api
      .get(`/stores/${currentStoreId}/categories`)
      .then((data) => setCategories(Array.isArray(data) ? data : []))
      .catch((err) => error("Không tải được danh mục", getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [currentStoreId, error]);

  useEffect(() => {
    load();
  }, [load]);

  // Resume polling if a sync is already running (e.g. after navigating back).
  useEffect(() => {
    if (!currentStoreId) return;
    api
      .get(`/stores/${currentStoreId}/categories/sync/status`)
      .then((st) => {
        if (st?.status === "running") setSyncing(true);
      })
      .catch(() => {});
  }, [currentStoreId]);

  const pollStatus = useCallback(async (): Promise<boolean> => {
    if (!currentStoreId) return true;
    try {
      const st = await api.get(`/stores/${currentStoreId}/categories/sync/status`);
      setProgress({ total_scanned: st?.total_scanned ?? 0, categories_found: st?.categories_found ?? 0 });
      if (st?.status === "running") return false;
      if (st?.status === "completed") {
        success("Đồng bộ danh mục xong", `Đã quét ${st.total_scanned} thẻ, tìm thấy ${st.categories_found} danh mục.`);
      } else if (st?.status === "failed") {
        error("Đồng bộ thất bại", st?.last_error || "Vui lòng thử lại.");
      } else if (st?.status === "interrupted") {
        error("Đồng bộ bị gián đoạn", "Hãy bấm đồng bộ lại.");
      }
      return true;
    } catch (err) {
      error("Không lấy được trạng thái đồng bộ", getErrorMessage(err));
      return true;
    }
  }, [currentStoreId, success, error]);

  // Poll the sync status while a job is running.
  useEffect(() => {
    if (!syncing) return;
    let active = true;
    const tick = async () => {
      const done = await pollStatus();
      if (done && active) {
        setSyncing(false);
        setProgress(null);
        load();
      }
    };
    const id = setInterval(tick, 2000);
    tick();
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [syncing, pollStatus, load]);

  const handleSync = async () => {
    if (!currentStoreId || syncing) return;
    try {
      await api.post(`/stores/${currentStoreId}/categories/sync`);
      setProgress({ total_scanned: 0, categories_found: 0 });
      setSyncing(true);
    } catch (err) {
      error("Không bắt đầu được đồng bộ", getErrorMessage(err));
    }
  };

  if (!currentStoreId) {
    return (
      <div className="mx-auto max-w-3xl">
        <p className="text-sm text-zinc-500">Hãy chọn một shop để quản lý danh mục.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-950">Danh mục shop</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Đồng bộ danh mục và mã TN VED shop đang dùng. AI chỉ chọn trong danh sách này khi tạo bài.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setAddOpen(true)} disabled={syncing}>
            <Plus size={16} /> Thêm danh mục
          </Button>
          <Button variant="brand" isLoading={syncing} disabled={syncing} onClick={handleSync}>
            <FolderSync size={16} /> Đồng bộ danh mục
          </Button>
        </div>
      </div>

      {syncing && (
        <div className="mb-4 rounded-xl border border-indigo-200 bg-indigo-50/70 px-4 py-3 text-sm text-indigo-700">
          Đang đồng bộ từ Wildberries… đã quét {progress?.total_scanned ?? 0} thẻ, tìm thấy{" "}
          {progress?.categories_found ?? 0} danh mục. Bạn có thể rời trang, quá trình vẫn chạy.
        </div>
      )}

      <div className="rounded-2xl border border-zinc-200 bg-white shadow-soft-sm">
        <div className="flex items-center justify-between border-b border-zinc-100 px-5 py-3">
          <span className="text-sm font-medium text-zinc-700">
            {categories.length} danh mục
          </span>
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-800 disabled:opacity-50"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Tải lại
          </button>
        </div>

        {categories.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-zinc-500">
            {loading
              ? "Đang tải…"
              : "Chưa có danh mục nào. Bấm “Đồng bộ danh mục” để lấy từ sản phẩm shop đang bán."}
          </div>
        ) : (
          <div className="divide-y divide-zinc-100">
            {categories.map((cat) => (
              <CategoryRow
                key={cat.id}
                storeId={currentStoreId}
                category={cat}
                onChanged={(updated) =>
                  setCategories((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
                }
                onDelete={() => setDeleteTarget(cat)}
              />
            ))}
          </div>
        )}
      </div>

      <Modal isOpen={addOpen} onClose={() => setAddOpen(false)} title="Thêm danh mục thủ công">
        <AddCategoryForm
          storeId={currentStoreId}
          existingIds={categories.map((c) => c.subject_id)}
          onClose={() => setAddOpen(false)}
          onAdded={(created) => {
            setCategories((prev) => [created, ...prev]);
            setAddOpen(false);
          }}
        />
      </Modal>

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="Xóa danh mục"
        description={`Xóa “${deleteTarget?.subject_name || deleteTarget?.subject_id}” khỏi danh mục shop? AI sẽ không còn chọn danh mục này.`}
        confirmLabel="Xóa"
        onCancel={() => setDeleteTarget(null)}
        onConfirm={async () => {
          if (!deleteTarget) return;
          try {
            await api.delete(`/stores/${currentStoreId}/categories/${deleteTarget.id}`);
            setCategories((prev) => prev.filter((c) => c.id !== deleteTarget.id));
            success("Đã xóa danh mục");
          } catch (err) {
            error("Không xóa được", getErrorMessage(err));
          } finally {
            setDeleteTarget(null);
          }
        }}
      />
    </div>
  );
}

function CategoryRow({
  storeId,
  category,
  onChanged,
  onDelete,
}: {
  storeId: number;
  category: StoreCategory;
  onChanged: (cat: StoreCategory) => void;
  onDelete: () => void;
}) {
  const { success, error } = useToast();
  const [tnved, setTnved] = useState(category.tnved ?? "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTnved(category.tnved ?? "");
  }, [category.tnved]);

  const dirty = (tnved || "") !== (category.tnved ?? "");

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api.patch(`/stores/${storeId}/categories/${category.id}`, {
        tnved: tnved.trim(),
      });
      onChanged(updated);
      success("Đã lưu mã TN VED");
    } catch (err) {
      error("Không lưu được", getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-zinc-900">
            {category.subject_name || `Subject ${category.subject_id}`}
          </span>
          {category.locked && <Lock size={13} className="text-amber-500" />}
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
              category.source === "manual"
                ? "bg-indigo-50 text-indigo-600"
                : "bg-zinc-100 text-zinc-500"
            }`}
          >
            {category.source === "manual" ? "thủ công" : "tự động"}
          </span>
        </div>
        <p className="mt-0.5 text-xs text-zinc-400">
          ID {category.subject_id} · {category.product_count} sản phẩm
          {category.tnved_options.length > 1 &&
            ` · ${category.tnved_options.length} mã TN VED đã dùng`}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Input
          value={tnved}
          onChange={(e) => setTnved(e.target.value)}
          placeholder="Mã TN VED"
          className="w-40 font-mono"
        />
        <Button variant="brand" size="sm" isLoading={saving} disabled={!dirty} onClick={save}>
          Lưu
        </Button>
        <button
          onClick={onDelete}
          className="rounded-lg p-2 text-zinc-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
          aria-label="Xóa danh mục"
        >
          <Trash2 size={16} />
        </button>
      </div>
    </div>
  );
}

function AddCategoryForm({
  storeId,
  existingIds,
  onClose,
  onAdded,
}: {
  storeId: number;
  existingIds: number[];
  onClose: () => void;
  onAdded: (cat: StoreCategory) => void;
}) {
  const { error } = useToast();
  const [subjectId, setSubjectId] = useState<number | null>(null);
  const [subjectName, setSubjectName] = useState("");
  const [tnved, setTnved] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!subjectId) {
      error("Hãy chọn một danh mục");
      return;
    }
    if (existingIds.includes(subjectId)) {
      error("Danh mục này đã có trong danh sách");
      return;
    }
    setSaving(true);
    try {
      const created = await api.post(`/stores/${storeId}/categories`, {
        subject_id: subjectId,
        subject_name: subjectName || null,
        tnved: tnved.trim() || null,
      });
      onAdded(created);
    } catch (err) {
      error("Không thêm được danh mục", getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <CategorySelector
        storeId={storeId}
        onSubjectSelected={(id, name) => {
          setSubjectId(id);
          setSubjectName(name);
        }}
      />
      <Input
        label="Mã TN VED (tùy chọn)"
        value={tnved}
        onChange={(e) => setTnved(e.target.value)}
        placeholder="VD: 6204628990"
        className="font-mono"
      />
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button variant="outline" onClick={onClose} disabled={saving}>
          Hủy
        </Button>
        <Button variant="brand" isLoading={saving} onClick={submit}>
          Thêm
        </Button>
      </div>
    </div>
  );
}
