"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { AdminShell } from "@/components/admin/AdminShell";
import { useToast } from "@/contexts/ToastContext";
import { api } from "@/lib/api";

type AiSettings = {
  default_image_model: string;
  fallback_image_model: string | null;
  gemini_model: string;
  max_retry: number;
  default_quantity: number;
  realism_threshold: number;
  validation_threshold: number;
  validation_failure_behavior: "block" | "warn";
  allow_legacy_vton: boolean;
  openai_configured: boolean;
  fal_configured: boolean;
  gemini_configured: boolean;
};

export default function AdminAiSettingsPage() {
  const { success, error } = useToast();
  const [settings, setSettings] = useState<AiSettings | null>(null);

  useEffect(() => {
    api.get("/admin/settings/ai").then(setSettings).catch(() => setSettings(null));
  }, []);

  const save = async () => {
    if (!settings) return;
    try {
      await api.put("/admin/settings/ai", {
        default_image_model: settings.default_image_model,
        fallback_image_model: settings.fallback_image_model || null,
        gemini_model: settings.gemini_model,
        max_retry: Number(settings.max_retry),
        default_quantity: Number(settings.default_quantity),
        realism_threshold: Number(settings.realism_threshold),
        validation_threshold: Number(settings.validation_threshold),
        validation_failure_behavior: settings.validation_failure_behavior,
        allow_legacy_vton: settings.allow_legacy_vton,
      });
      success("Settings updated");
    } catch (err) {
      error("Save failed", err instanceof Error ? err.message : "Request failed");
    }
  };

  return (
    <AdminShell title="AI Settings" subtitle="Model defaults, retry policy, and validation thresholds without exposing sensitive API keys.">
      {settings ? (
        <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
          <section className="rounded-[24px] border border-stone-200 bg-stone-50/80 p-5">
            <div className="space-y-3">
              <Input label="Default image model" value={settings.default_image_model} onChange={(e) => setSettings({ ...settings, default_image_model: e.target.value })} />
              <Input label="Fallback image model" value={settings.fallback_image_model || ""} onChange={(e) => setSettings({ ...settings, fallback_image_model: e.target.value || null })} />
              <Input label="Gemini model" value={settings.gemini_model} onChange={(e) => setSettings({ ...settings, gemini_model: e.target.value })} />
              <Input label="Max retry" type="number" value={String(settings.max_retry)} onChange={(e) => setSettings({ ...settings, max_retry: Number(e.target.value) })} />
              <Input label="Default quantity" type="number" value={String(settings.default_quantity)} onChange={(e) => setSettings({ ...settings, default_quantity: Number(e.target.value) })} />
              <Input label="Realism threshold" type="number" value={String(settings.realism_threshold)} onChange={(e) => setSettings({ ...settings, realism_threshold: Number(e.target.value) })} />
              <Input label="Validation threshold" type="number" value={String(settings.validation_threshold)} onChange={(e) => setSettings({ ...settings, validation_threshold: Number(e.target.value) })} />
              <label className="block text-sm font-medium text-stone-700">
                Validation failure behavior
                <select
                  value={settings.validation_failure_behavior}
                  onChange={(e) => setSettings({ ...settings, validation_failure_behavior: e.target.value as "block" | "warn" })}
                  className="mt-1 block w-full rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm"
                >
                  <option value="warn">Warn and return all images</option>
                  <option value="block">Strict block mode</option>
                </select>
              </label>
              <label className="flex items-center gap-2 text-sm text-stone-700">
                <input type="checkbox" checked={settings.allow_legacy_vton} onChange={(e) => setSettings({ ...settings, allow_legacy_vton: e.target.checked })} />
                Allow legacy VTON
              </label>
              <Button variant="brand" onClick={save}>Save settings</Button>
            </div>
          </section>
          <section className="grid gap-4 md:grid-cols-3">
            <div className="rounded-[24px] border border-stone-200 p-5">
              <p className="text-xs uppercase tracking-[0.24em] text-stone-400">OpenAI key</p>
              <p className="mt-3 text-xl font-semibold text-stone-950">{settings.openai_configured ? "Configured" : "Missing"}</p>
            </div>
            <div className="rounded-[24px] border border-stone-200 p-5">
              <p className="text-xs uppercase tracking-[0.24em] text-stone-400">Fal key</p>
              <p className="mt-3 text-xl font-semibold text-stone-950">{settings.fal_configured ? "Configured" : "Missing"}</p>
            </div>
            <div className="rounded-[24px] border border-stone-200 p-5">
              <p className="text-xs uppercase tracking-[0.24em] text-stone-400">Gemini key</p>
              <p className="mt-3 text-xl font-semibold text-stone-950">{settings.gemini_configured ? "Configured" : "Missing"}</p>
            </div>
          </section>
        </div>
      ) : null}
    </AdminShell>
  );
}
