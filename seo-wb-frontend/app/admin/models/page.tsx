"use client";

import Image from "next/image";
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
  status: string;
  quality_status: "draft" | "approved" | "rejected";
  is_ai_generated: boolean;
  poses?: Record<string, string>;
  reference_image_url?: string | null;
};

const initialForm = {
  id: "",
  name: "",
  gender: "female",
  body_type: "average",
  status: "active",
  quality_status: "draft" as const,
  is_ai_generated: false,
  height_cm: "",
  weight_kg: "",
};

export default function AdminModelsPage() {
  const { success, error } = useToast();
  const [models, setModels] = useState<ModelTemplate[]>([]);
  const [form, setForm] = useState(initialForm);
  const [referenceImage, setReferenceImage] = useState<File | null>(null);

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

  const submit = async () => {
    const body = new FormData();
    body.set("payload_json", JSON.stringify({
      id: form.id,
      name: form.name,
      gender: form.gender,
      body_type: form.body_type,
      height_cm: form.height_cm ? Number(form.height_cm) : null,
      weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
      is_ai_generated: form.is_ai_generated,
      status: form.status,
      quality_status: form.quality_status,
      poses: {},
    }));
    if (referenceImage) body.set("reference_image", referenceImage);
    try {
      await api.post("/admin/models", body);
      setForm(initialForm);
      setReferenceImage(null);
      await load();
      success("Model saved");
    } catch (err) {
      error("Save failed", err instanceof Error ? err.message : "Request failed");
    }
  };

  const updateQualityStatus = async (model: ModelTemplate, qualityStatus: ModelTemplate["quality_status"]) => {
    const body = new FormData();
    body.set("payload_json", JSON.stringify({
      id: model.id,
      name: model.name,
      gender: model.gender,
      body_type: model.body_type,
      height_cm: model.height_cm ?? null,
      weight_kg: model.weight_kg ?? null,
      is_ai_generated: model.is_ai_generated,
      status: model.status,
      quality_status: qualityStatus,
      poses: model.poses || {},
    }));
    try {
      await api.put(`/admin/models/${model.id}`, body);
      await load();
      success(`Model ${qualityStatus}`);
    } catch (err) {
      error("Update failed", err instanceof Error ? err.message : "Request failed");
    }
  };

  const deleteModel = async (id: string) => {
    try {
      await api.delete(`/admin/models/${id}`);
      await load();
      success("Model deleted");
    } catch (err) {
      error("Delete failed", err instanceof Error ? err.message : "Request failed");
    }
  };

  return (
    <AdminShell title="Models" subtitle="Manage reusable model templates and upload their reference imagery for generation workflows.">
      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <section className="rounded-[24px] border border-stone-200 bg-stone-50/80 p-5">
          <h3 className="text-lg font-semibold text-stone-950">Create model</h3>
          <div className="mt-4 space-y-3">
            <Input label="ID" value={form.id} onChange={(e) => setForm((s) => ({ ...s, id: e.target.value }))} />
            <Input label="Name" value={form.name} onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))} />
            <Input label="Gender" value={form.gender} onChange={(e) => setForm((s) => ({ ...s, gender: e.target.value }))} />
            <Input label="Body type" value={form.body_type} onChange={(e) => setForm((s) => ({ ...s, body_type: e.target.value }))} />
            <Input label="Height cm" type="number" value={form.height_cm} onChange={(e) => setForm((s) => ({ ...s, height_cm: e.target.value }))} />
            <Input label="Weight kg" type="number" value={form.weight_kg} onChange={(e) => setForm((s) => ({ ...s, weight_kg: e.target.value }))} />
            <label className="block text-sm font-medium text-stone-700">
              Quality status
              <select
                className="mt-1 block w-full rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm"
                value={form.quality_status}
                onChange={(e) => setForm((s) => ({ ...s, quality_status: e.target.value as typeof s.quality_status }))}
              >
                <option value="draft">Draft</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
            </label>
            <label className="block text-sm font-medium text-stone-700">
              Reference image
              <input className="mt-1 block w-full rounded-lg border border-stone-200 px-3 py-2 text-sm" type="file" accept=".jpg,.jpeg,.png,.webp" onChange={(e: ChangeEvent<HTMLInputElement>) => setReferenceImage(e.target.files?.[0] || null)} />
            </label>
            <label className="flex items-center gap-2 text-sm text-stone-700">
              <input type="checkbox" checked={form.is_ai_generated} onChange={(e) => setForm((s) => ({ ...s, is_ai_generated: e.target.checked }))} />
              Mark as AI-generated
            </label>
            <Button variant="brand" className="w-full" onClick={submit}>Save model</Button>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          {models.map((model) => (
            <article key={model.id} className="rounded-[24px] border border-stone-200 bg-white p-5">
              {model.reference_image_url ? (
                <Image src={`${API_BASE.replace("/api/v1", "")}${model.reference_image_url}`} alt={model.name} width={640} height={640} className="h-56 w-full rounded-2xl object-cover" />
              ) : (
                <div className="flex h-56 items-center justify-center rounded-2xl bg-stone-100 text-stone-400">No image</div>
              )}
              <div className="mt-4">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-lg font-semibold text-stone-950">{model.name}</h3>
                  <span className="rounded-full bg-stone-100 px-3 py-1 text-xs uppercase tracking-[0.2em] text-stone-500">{model.status}</span>
                </div>
                <p className="mt-2 text-sm text-stone-500">{model.gender} / {model.body_type}</p>
                <p className="mt-2 text-sm text-stone-500">Quality: <span className="font-medium text-stone-700">{model.quality_status}</span></p>
                {model.is_ai_generated ? (
                  <p className="mt-3 rounded-2xl bg-amber-50 px-3 py-2 text-sm text-amber-800">AI-generated template. User-facing realism warning should be shown.</p>
                ) : null}
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => updateQualityStatus(model, "approved")}>Approve</Button>
                  <Button size="sm" variant="outline" onClick={() => updateQualityStatus(model, "rejected")}>Reject</Button>
                  <Button size="sm" variant="ghost" onClick={load}>Refresh</Button>
                  <Button size="sm" variant="danger" onClick={() => deleteModel(model.id)}>Delete</Button>
                </div>
              </div>
            </article>
          ))}
        </section>
      </div>
    </AdminShell>
  );
}
