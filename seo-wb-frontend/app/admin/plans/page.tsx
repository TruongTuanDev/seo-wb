"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { AdminShell } from "@/components/admin/AdminShell";
import { useToast } from "@/contexts/ToastContext";
import { api } from "@/lib/api";

type Plan = {
  id: number;
  code: string;
  name: string;
  price: number;
  currency: string;
  monthly_quota: number; // cards / month
  monthly_credits: number; // images / month
  monthly_cost_limit: number | null;
  max_images_per_job: number;
  allow_legacy_vton: boolean;
  allow_gpt_image: boolean;
  priority_queue: boolean;
  is_active: boolean;
};

function errMessage(err: unknown) {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "Unknown error";
}

export default function AdminPlansPage() {
  const { success, error } = useToast();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingCode, setSavingCode] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.get("/admin/plans");
      setPlans(Array.isArray(data) ? data : []);
    } catch (err) {
      error("Could not load plans", errMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const patch = <K extends keyof Plan>(code: string, field: K, value: Plan[K]) =>
    setPlans((prev) => prev.map((p) => (p.code === code ? { ...p, [field]: value } : p)));

  const save = async (plan: Plan) => {
    setSavingCode(plan.code);
    try {
      const updated = await api.put(`/admin/plans/${plan.code}`, {
        name: plan.name,
        price: Number(plan.price),
        currency: plan.currency,
        monthly_quota: Number(plan.monthly_quota),
        monthly_credits: Number(plan.monthly_credits),
        monthly_cost_limit: plan.monthly_cost_limit === null ? null : Number(plan.monthly_cost_limit),
        max_images_per_job: Number(plan.max_images_per_job),
        allow_legacy_vton: plan.allow_legacy_vton,
        allow_gpt_image: plan.allow_gpt_image,
        priority_queue: plan.priority_queue,
        is_active: plan.is_active,
      });
      setPlans((prev) => prev.map((p) => (p.code === plan.code ? updated : p)));
      success("Plan saved", `${plan.name} updated.`);
    } catch (err) {
      error("Could not save plan", errMessage(err));
    } finally {
      setSavingCode(null);
    }
  };

  return (
    <AdminShell
      title="Plans"
      subtitle="Edit plan price, card quota, image quota and limits. Changes apply to NEW subscribers; existing users keep their current quota until you adjust them per-user."
    >
      <div className="space-y-4">
        {loading && plans.length === 0 && <p className="text-sm text-stone-500">Loading…</p>}
        {!loading && plans.length === 0 && <p className="text-sm text-stone-500">No plans found.</p>}

        {plans.map((plan) => (
          <div key={plan.code} className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <span className="text-xs uppercase tracking-[0.2em] text-stone-400">{plan.code}</span>
                <h3 className="text-lg font-semibold text-stone-950">{plan.name}</h3>
              </div>
              <label className="flex items-center gap-2 text-sm text-stone-700">
                <input
                  type="checkbox"
                  checked={plan.is_active}
                  onChange={(e) => patch(plan.code, "is_active", e.target.checked)}
                />
                Active
              </label>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Input label="Name" value={plan.name} onChange={(e) => patch(plan.code, "name", e.target.value)} />
              <Input
                label="Price"
                type="number"
                value={plan.price}
                onChange={(e) => patch(plan.code, "price", e.target.value === "" ? 0 : Number(e.target.value))}
              />
              <Input
                label="Currency"
                value={plan.currency}
                onChange={(e) => patch(plan.code, "currency", e.target.value)}
              />
              <Input
                label="Cards / month"
                type="number"
                value={plan.monthly_quota}
                onChange={(e) => patch(plan.code, "monthly_quota", e.target.value === "" ? 0 : Number(e.target.value))}
              />
              <Input
                label="Images / month"
                type="number"
                value={plan.monthly_credits}
                onChange={(e) => patch(plan.code, "monthly_credits", e.target.value === "" ? 0 : Number(e.target.value))}
              />
              <Input
                label="Max images / job"
                type="number"
                value={plan.max_images_per_job}
                onChange={(e) =>
                  patch(plan.code, "max_images_per_job", e.target.value === "" ? 1 : Number(e.target.value))
                }
              />
              <Input
                label="Monthly cost limit (blank = none)"
                type="number"
                value={plan.monthly_cost_limit ?? ""}
                onChange={(e) =>
                  patch(plan.code, "monthly_cost_limit", e.target.value === "" ? null : Number(e.target.value))
                }
              />
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-4 text-sm text-stone-700">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={plan.allow_gpt_image}
                  onChange={(e) => patch(plan.code, "allow_gpt_image", e.target.checked)}
                />
                GPT image
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={plan.allow_legacy_vton}
                  onChange={(e) => patch(plan.code, "allow_legacy_vton", e.target.checked)}
                />
                Legacy VTON
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={plan.priority_queue}
                  onChange={(e) => patch(plan.code, "priority_queue", e.target.checked)}
                />
                Priority queue
              </label>
              <div className="ml-auto">
                <Button variant="brand" isLoading={savingCode === plan.code} onClick={() => save(plan)}>
                  Save
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </AdminShell>
  );
}
