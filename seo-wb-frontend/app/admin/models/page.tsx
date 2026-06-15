"use client";

import { ChangeEvent, startTransition, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { AdminShell } from "@/components/admin/AdminShell";
import { useToast } from "@/contexts/ToastContext";
import { api, API_BASE } from "@/lib/api";

type ModelTemplate = {
  id: string;
  name: string;
  gender: string;
  body_type: string;
  height_cm?: number | null;
  weight_kg?: number | null;
  garment_type?: string | null;
  status: string;
  quality_status: "draft" | "approved" | "rejected";
  is_ai_generated: boolean;
  poses?: Record<string, string>;
  reference_image_url?: string | null;
};

const initialForm = {
  name: "",
  garment_type: "",
};

const slugify = (text: string) => {
  return text
    .toString()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "-")
    .replace(/[^\w-]+/g, "")
    .replace(/--+/g, "-");
};

const getGarmentTypeLabel = (type: string | null | undefined) => {
  switch (type) {
    case "dress":
      return "Váy";
    case "pants":
      return "Quần";
    case "shirt":
      return "Áo";
    case "shoes":
      return "Giày";
    case "suit":
      return "Bộ quần áo";
    default:
      return "Chưa phân loại";
  }
};

const getImageUrl = (url: string | null | undefined) => {
  if (!url) return "";
  if (url.startsWith("/storage")) {
    return `${API_BASE.replace("/api/v1", "")}${url}`;
  }
  return url; // Static public assets like /models/... loaded relatively from frontend origin
};

function ModelCard({ model, onEdit, onDelete }: { model: ModelTemplate; onEdit: (model: ModelTemplate) => void; onDelete: (id: string) => void }) {
  const [activeImage, setActiveImage] = useState<string | null>(model.reference_image_url || null);

  useEffect(() => {
    queueMicrotask(() => setActiveImage(model.reference_image_url || null));
  }, [model.reference_image_url]);

  return (
    <article className="rounded-[24px] border border-stone-200 bg-white p-5 flex flex-col justify-between">
      <div>
        <div className="relative">
          {activeImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={getImageUrl(activeImage)}
              alt={model.name}
              className="h-56 w-full rounded-2xl object-cover transition-all duration-300"
            />
          ) : (
            <div className="flex h-56 items-center justify-center rounded-2xl bg-stone-100 text-stone-400">Không có ảnh</div>
          )}
        </div>

        {model.poses && Object.keys(model.poses).length > 0 && (
          <div className="mt-3 flex gap-2 overflow-x-auto pb-1 max-w-full scrollbar-thin">
            {model.reference_image_url && (
              <button
                type="button"
                onClick={() => setActiveImage(model.reference_image_url || null)}
                className={`relative h-12 w-12 flex-shrink-0 rounded-lg overflow-hidden border transition-all ${
                  activeImage === model.reference_image_url ? "border-indigo-600 ring-2 ring-indigo-100" : "border-stone-200"
                }`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={getImageUrl(model.reference_image_url)}
                  alt="Ảnh chính"
                  className="object-cover w-full h-full"
                />
              </button>
            )}
            {Object.entries(model.poses).map(([poseName, url]) => {
              if (url === model.reference_image_url) return null;
              return (
                <button
                  key={poseName}
                  type="button"
                  onClick={() => setActiveImage(url)}
                  className={`relative h-12 w-12 flex-shrink-0 rounded-lg overflow-hidden border transition-all ${
                    activeImage === url ? "border-indigo-600 ring-2 ring-indigo-100" : "border-stone-200"
                  }`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={getImageUrl(url)}
                    alt={poseName}
                    className="object-cover w-full h-full"
                  />
                </button>
              );
            })}
          </div>
        )}

        <div className="mt-4">
          <h3 className="text-lg font-semibold text-stone-950">{model.name}</h3>
          <p className="mt-1 text-sm text-stone-500">
            Loại: <span className="font-medium text-stone-700">{getGarmentTypeLabel(model.garment_type)}</span>
          </p>
        </div>
      </div>
      <div className="mt-4 flex gap-2 justify-end">
        <Button size="sm" variant="outline" onClick={() => onEdit(model)}>Sửa</Button>
        <Button size="sm" variant="danger" onClick={() => onDelete(model.id)}>Xóa</Button>
      </div>
    </article>
  );
}

export default function AdminModelsPage() {
  const { success, error } = useToast();
  const [models, setModels] = useState<ModelTemplate[]>([]);
  const [form, setForm] = useState(initialForm);
  const [referenceImages, setReferenceImages] = useState<File[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingPoses, setEditingPoses] = useState<Record<string, string>>({});

  const load = async () => {
    setModels(await api.get("/admin/models"));
  };

  useEffect(() => {
    api.get("/admin/models")
      .then((response) => {
        startTransition(() => setModels(response));
      })
      .catch(() => {
        startTransition(() => setModels([]));
      });
  }, []);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setReferenceImages(Array.from(e.target.files));
    } else {
      setReferenceImages([]);
    }
  };

  const startEdit = (model: ModelTemplate) => {
    setEditingId(model.id);
    setForm({
      name: model.name,
      garment_type: model.garment_type || "",
    });
    setEditingPoses(model.poses || {});
    setReferenceImages([]);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(initialForm);
    setEditingPoses({});
    setReferenceImages([]);
  };

  const submit = async () => {
    if (!form.name.trim()) {
      error("Lỗi", "Vui lòng nhập tên thẻ");
      return;
    }
    const isEdit = !!editingId;
    if (!isEdit && referenceImages.length === 0) {
      error("Lỗi", "Vui lòng tải lên ít nhất một ảnh");
      return;
    }
    const slug = isEdit ? editingId : (slugify(form.name) || `model-${Math.random().toString(36).substring(2, 7)}`);
    const body = new FormData();
    body.set("payload_json", JSON.stringify({
      id: slug,
      name: form.name,
      gender: "female",
      body_type: "average",
      height_cm: null,
      weight_kg: null,
      garment_type: form.garment_type || null,
      is_ai_generated: false,
      status: "active",
      quality_status: "approved",
      poses: isEdit ? editingPoses : {},
    }));

    if (referenceImages[0]) {
      body.set("reference_image", referenceImages[0]);
      body.set("front_pose", referenceImages[0]);
    }
    if (referenceImages[1]) body.set("side_45_pose", referenceImages[1]);
    if (referenceImages[2]) body.set("walking_pose", referenceImages[2]);
    if (referenceImages[3]) body.set("back_pose", referenceImages[3]);
    if (referenceImages[4]) body.set("hand_on_hip_pose", referenceImages[4]);
    if (referenceImages[5]) body.set("sitting_pose", referenceImages[5]);

    try {
      if (isEdit) {
        await api.put(`/admin/models/${editingId}`, body);
        success("Đã cập nhật model");
      } else {
        await api.post("/admin/models", body);
        success("Đã lưu model");
      }
      setForm(initialForm);
      setEditingId(null);
      setEditingPoses({});
      setReferenceImages([]);
      await load();
    } catch (err) {
      error(isEdit ? "Cập nhật thất bại" : "Lưu thất bại", err instanceof Error ? err.message : "Có lỗi xảy ra");
    }
  };

  const deleteModel = async (id: string) => {
    try {
      await api.delete(`/admin/models/${id}`);
      await load();
      success("Đã xóa model");
    } catch (err) {
      error("Xóa thất bại", err instanceof Error ? err.message : "Có lỗi xảy ra");
    }
  };

  return (
    <AdminShell title="Models" subtitle="Quản lý các model mẫu và tải lên hình ảnh tham chiếu để thay trang phục.">
      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <section className="rounded-[24px] border border-stone-200 bg-stone-50/80 p-5 h-fit">
          <h3 className="text-lg font-semibold text-stone-950">
            {editingId ? "Sửa model" : "Tạo model mới"}
          </h3>
          <div className="mt-4 space-y-3">
            <Input label="Tên thẻ" value={form.name} onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))} placeholder="Nhập tên thẻ model..." />
            
            <label className="block text-sm font-medium text-stone-700">
              Loại model
              <select
                className="mt-1 block w-full rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm"
                value={form.garment_type}
                onChange={(e) => setForm((s) => ({ ...s, garment_type: e.target.value }))}
              >
                <option value="">Chọn loại model...</option>
                <option value="dress">Váy (Dress/Skirt)</option>
                <option value="pants">Quần (Pants/Shorts)</option>
                <option value="shirt">Áo (Shirt/Top)</option>
                <option value="shoes">Giày (Shoes)</option>
                <option value="suit">Bộ quần áo (Suit/Outfit)</option>
              </select>
            </label>
            
            <label className="block text-sm font-medium text-stone-700">
              Tải ảnh lên {editingId ? "(Để trống nếu không muốn đổi ảnh)" : "(Có thể chọn nhiều ảnh)"}
              <input 
                className="mt-1 block w-full rounded-lg border border-stone-200 px-3 py-2 text-sm" 
                type="file" 
                multiple 
                accept=".jpg,.jpeg,.png,.webp" 
                onChange={handleFileChange} 
              />
              <span className="text-xs text-stone-400 mt-1 block">Tải lên tối đa 6 ảnh. Ảnh đầu tiên sẽ là ảnh chính.</span>
            </label>

            {referenceImages.length > 0 && (
              <div className="mt-2 text-xs text-stone-500 bg-stone-100 p-2.5 rounded-lg space-y-1">
                <p className="font-semibold text-stone-700">Đã chọn {referenceImages.length} ảnh:</p>
                <div className="grid grid-cols-5 gap-1.5 max-h-24 overflow-y-auto">
                  {referenceImages.map((file, idx) => {
                    let previewUrl = "";
                    try {
                      previewUrl = URL.createObjectURL(file);
                    } catch {}
                    return (
                      <div key={idx} className="relative aspect-square w-full rounded border border-stone-200 overflow-hidden bg-white" title={file.name}>
                        {previewUrl ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={previewUrl}
                            alt={file.name}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="h-full w-full bg-stone-200" />
                        )}
                        <span className="absolute bottom-0 left-0 right-0 bg-black/60 text-[8px] text-white text-center truncate px-0.5 font-bold">
                          {idx === 0 ? "Chính" : `#${idx + 1}`}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            
            <div className="flex gap-2 mt-4">
              {editingId && (
                <Button variant="outline" className="flex-1" onClick={cancelEdit}>Hủy</Button>
              )}
              <Button variant="brand" className="flex-1" onClick={submit}>
                {editingId ? "Cập nhật" : "Lưu model"}
              </Button>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          {models.map((model) => (
            <ModelCard key={model.id} model={model} onEdit={startEdit} onDelete={deleteModel} />
          ))}
        </section>
      </div>
    </AdminShell>
  );
}
