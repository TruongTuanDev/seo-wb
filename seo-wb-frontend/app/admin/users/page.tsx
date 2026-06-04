"use client";

import { startTransition, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { AdminShell } from "@/components/admin/AdminShell";
import { useToast } from "@/contexts/ToastContext";
import { api } from "@/lib/api";

type AdminUser = {
  id: number;
  name: string;
  email: string;
  role: string;
  status: string;
  plan_type: string;
  max_images_per_job: number;
  allow_legacy_vton: boolean;
  allow_gpt_image: boolean;
  priority_queue: boolean;
  monthly_quota: number;
  used_quota: number;
  monthly_card_quota: number;
  used_card_quota: number;
  monthly_cost_limit: number | null;
  used_cost: number;
  credit_balance: number;
  credits_used: number;
  credits_granted: number;
  quota_reset_at: string | null;
  last_quota_reset_at: string | null;
  close_to_quota_limit: boolean;
  close_to_cost_limit: boolean;
};

const emptyForm = { name: "", email: "", password: "", role: "user", plan_type: "free", monthly_quota: "30", monthly_card_quota: "10", monthly_cost_limit: "5" };

const PLAN_OPTIONS = [
  { value: "free", label: "Free" },
  { value: "pro", label: "Pro" },
  { value: "agency", label: "Agency" },
];

const PLAN_DEFAULTS: Record<string, { monthly_quota: string; monthly_card_quota: string; monthly_cost_limit: string }> = {
  free: { monthly_quota: "30", monthly_card_quota: "10", monthly_cost_limit: "5" },
  pro: { monthly_quota: "500", monthly_card_quota: "50", monthly_cost_limit: "50" },
  agency: { monthly_quota: "3000", monthly_card_quota: "500", monthly_cost_limit: "300" },
};

export default function AdminUsersPage() {
  const { success, error } = useToast();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState(emptyForm);

  const load = async () => {
    const query = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
    const response = await api.get(`/admin/users${query}`);
    setUsers(response);
  };

  useEffect(() => {
    api.get("/admin/users")
      .then((response) => {
        startTransition(() => setUsers(response));
      })
      .catch(() => {
        startTransition(() => setUsers([]));
      });
  }, []);

  const createUser = async () => {
    try {
      await api.post("/admin/users", {
        ...form,
        monthly_quota: Number(form.monthly_quota) || 0,
        monthly_card_quota: Number(form.monthly_card_quota) || 0,
        monthly_cost_limit: form.monthly_cost_limit.trim() ? Number(form.monthly_cost_limit) : null,
        status: "active",
      });
      setForm(emptyForm);
      await load();
      success("User created");
    } catch (err) {
      error("Create failed", err instanceof Error ? err.message : "Request failed");
    }
  };

  const updateUser = async (user: AdminUser, patch: Partial<AdminUser>) => {
    try {
      await api.put(`/admin/users/${user.id}`, patch);
      await load();
      success("User updated");
    } catch (err) {
      error("Update failed", err instanceof Error ? err.message : "Request failed");
    }
  };

  const resetQuota = async (userId: number) => {
    try {
      await api.post(`/admin/users/${userId}/reset-quota`);
      await load();
      success("Quota reset");
    } catch (err) {
      error("Reset failed", err instanceof Error ? err.message : "Request failed");
    }
  };

  const resetCost = async (userId: number) => {
    try {
      await api.post(`/admin/users/${userId}/reset-cost`);
      await load();
      success("Cost reset");
    } catch (err) {
      error("Reset failed", err instanceof Error ? err.message : "Request failed");
    }
  };

  const deleteUser = async (userId: number) => {
    try {
      await api.delete(`/admin/users/${userId}`);
      await load();
      success("User deleted");
    } catch (err) {
      error("Delete failed", err instanceof Error ? err.message : "Request failed");
    }
  };

  const quotaTone = (used: number, limit: number) => {
    if (limit <= 0) return "bg-zinc-200";
    const ratio = used / limit;
    if (ratio >= 1) return "bg-rose-500";
    if (ratio >= 0.8) return "bg-amber-500";
    return "bg-emerald-500";
  };

  const formatDate = (value: string | null) => {
    if (!value) return "Not scheduled";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString();
  };

  const handlePlanChange = (planType: string) => {
    const defaults = PLAN_DEFAULTS[planType] ?? PLAN_DEFAULTS.free;
    setForm((state) => ({
      ...state,
      plan_type: planType,
      monthly_quota: defaults.monthly_quota,
      monthly_card_quota: defaults.monthly_card_quota,
      monthly_cost_limit: defaults.monthly_cost_limit,
    }));
  };

  return (
    <AdminShell title="Users" subtitle="Search, create, suspend, promote, and adjust quotas without leaving the admin workspace.">
      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <section className="rounded-[24px] border border-stone-200 bg-stone-50/80 p-5">
          <h3 className="text-lg font-semibold text-stone-950">Create user</h3>
          <div className="mt-4 space-y-3">
            <Input label="Name" value={form.name} onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))} />
            <Input label="Email" type="email" value={form.email} onChange={(e) => setForm((s) => ({ ...s, email: e.target.value }))} />
            <Input label="Password" type="password" value={form.password} onChange={(e) => setForm((s) => ({ ...s, password: e.target.value }))} />
            <Input label="Role" value={form.role} onChange={(e) => setForm((s) => ({ ...s, role: e.target.value }))} />
            <label className="block text-sm font-medium text-stone-700">
              Plan
              <select className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm" value={form.plan_type} onChange={(e) => handlePlanChange(e.target.value)}>
                {PLAN_OPTIONS.map((plan) => (
                  <option key={plan.value} value={plan.value}>{plan.label}</option>
                ))}
              </select>
            </label>
            <Input label="Monthly quota (Images)" type="number" value={form.monthly_quota} onChange={(e) => setForm((s) => ({ ...s, monthly_quota: e.target.value }))} />
            <Input label="Monthly card quota (Posts)" type="number" value={form.monthly_card_quota} onChange={(e) => setForm((s) => ({ ...s, monthly_card_quota: e.target.value }))} />
            <Input label="Monthly cost limit (optional)" type="number" step="0.01" value={form.monthly_cost_limit} onChange={(e) => setForm((s) => ({ ...s, monthly_cost_limit: e.target.value }))} />
            <Button variant="brand" className="w-full" onClick={createUser}>Create user</Button>
          </div>
        </section>

        <section className="rounded-[24px] border border-stone-200">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 p-5">
            <Input label="Search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="name or email" className="max-w-sm" />
            <Button variant="outline" onClick={() => load().catch(() => undefined)}>Refresh</Button>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-stone-50 text-stone-500">
                <tr>
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Plan</th>
                  <th className="px-4 py-3">Image Quota</th>
                  <th className="px-4 py-3">Card Quota</th>
                  <th className="px-4 py-3">Cost Limit</th>
                  <th className="px-4 py-3">Credits</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-t border-stone-200">
                    <td className="px-4 py-3">
                      <div className="font-medium text-stone-950">{user.name}</div>
                      <div className="text-stone-500">{user.email}</div>
                    </td>
                    <td className="px-4 py-3">
                      <input className="w-28 rounded-lg border border-stone-200 px-2 py-1" value={user.role} onChange={(e) => setUsers((list) => list.map((item) => item.id === user.id ? { ...item, role: e.target.value } : item))} onBlur={(e) => updateUser(user, { role: e.target.value })} />
                    </td>
                    <td className="px-4 py-3">
                      <select className="rounded-lg border border-stone-200 px-2 py-1" value={user.status} onChange={(e) => updateUser(user, { status: e.target.value })}>
                        <option value="active">active</option>
                        <option value="suspended">suspended</option>
                      </select>
                    </td>
                    <td className="px-4 py-3 min-w-[220px]">
                      <div className="space-y-2">
                        <select className="w-full rounded-lg border border-stone-200 px-2 py-1" value={user.plan_type} onChange={(e) => updateUser(user, { plan_type: e.target.value })}>
                          {PLAN_OPTIONS.map((plan) => (
                            <option key={plan.value} value={plan.value}>{plan.label}</option>
                          ))}
                        </select>
                        <div className="text-xs text-stone-500">
                          Max/job: {user.max_images_per_job} · GPT: {user.allow_gpt_image ? "on" : "off"} · VTON: {user.allow_legacy_vton ? "on" : "off"}
                        </div>
                        <div className="text-xs text-stone-500">
                          Priority queue: {user.priority_queue ? "yes" : "no"} · Next reset: {formatDate(user.quota_reset_at)}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 min-w-[220px]">
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-stone-700">
                          {user.credit_balance} available / {user.credits_granted} granted
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          <input
                            className="w-full rounded-lg border border-stone-200 px-2 py-1"
                            type="number"
                            value={user.credit_balance}
                            onChange={(e) => setUsers((list) => list.map((item) => item.id === user.id ? { ...item, credit_balance: Number(e.target.value) || 0 } : item))}
                            onBlur={(e) => updateUser(user, { credit_balance: Number(e.target.value) || 0 })}
                          />
                          <input
                            className="w-full rounded-lg border border-stone-200 px-2 py-1"
                            type="number"
                            value={user.credits_used}
                            onChange={(e) => setUsers((list) => list.map((item) => item.id === user.id ? { ...item, credits_used: Number(e.target.value) || 0 } : item))}
                            onBlur={(e) => updateUser(user, { credits_used: Number(e.target.value) || 0 })}
                          />
                          <input
                            className="w-full rounded-lg border border-stone-200 px-2 py-1"
                            type="number"
                            value={user.credits_granted}
                            onChange={(e) => setUsers((list) => list.map((item) => item.id === user.id ? { ...item, credits_granted: Number(e.target.value) || 0 } : item))}
                            onBlur={(e) => updateUser(user, { credits_granted: Number(e.target.value) || 0 })}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 min-w-[220px]">
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-stone-700">{user.used_quota} / {user.monthly_quota}</div>
                        <div className="h-2 overflow-hidden rounded-full bg-stone-200">
                          <div
                            className={`h-full ${quotaTone(user.used_quota, user.monthly_quota)}`}
                            style={{ width: `${Math.min(100, user.monthly_quota > 0 ? (user.used_quota / user.monthly_quota) * 100 : 0)}%` }}
                          />
                        </div>
                        {user.close_to_quota_limit && <div className="text-xs font-medium text-amber-600">Close to quota limit</div>}
                        <div className="grid grid-cols-2 gap-2">
                          <input
                            className="w-full rounded-lg border border-stone-200 px-2 py-1"
                            type="number"
                            value={user.monthly_quota}
                            onChange={(e) => setUsers((list) => list.map((item) => item.id === user.id ? { ...item, monthly_quota: Number(e.target.value) || 0 } : item))}
                            onBlur={(e) => updateUser(user, { monthly_quota: Number(e.target.value) || 0 })}
                          />
                          <input
                            className="w-full rounded-lg border border-stone-200 px-2 py-1"
                            type="number"
                            value={user.used_quota}
                            onChange={(e) => setUsers((list) => list.map((item) => item.id === user.id ? { ...item, used_quota: Number(e.target.value) || 0 } : item))}
                            onBlur={(e) => updateUser(user, { used_quota: Number(e.target.value) || 0 })}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 min-w-[220px]">
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-stone-700">{user.used_card_quota} / {user.monthly_card_quota}</div>
                        <div className="h-2 overflow-hidden rounded-full bg-stone-200">
                          <div
                            className={`h-full ${quotaTone(user.used_card_quota, user.monthly_card_quota)}`}
                            style={{ width: `${Math.min(100, user.monthly_card_quota > 0 ? (user.used_card_quota / user.monthly_card_quota) * 100 : 0)}%` }}
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <input
                            className="w-full rounded-lg border border-stone-200 px-2 py-1"
                            type="number"
                            value={user.monthly_card_quota}
                            onChange={(e) => setUsers((list) => list.map((item) => item.id === user.id ? { ...item, monthly_card_quota: Number(e.target.value) || 0 } : item))}
                            onBlur={(e) => updateUser(user, { monthly_card_quota: Number(e.target.value) || 0 })}
                          />
                          <input
                            className="w-full rounded-lg border border-stone-200 px-2 py-1"
                            type="number"
                            value={user.used_card_quota}
                            onChange={(e) => setUsers((list) => list.map((item) => item.id === user.id ? { ...item, used_card_quota: Number(e.target.value) || 0 } : item))}
                            onBlur={(e) => updateUser(user, { used_card_quota: Number(e.target.value) || 0 })}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 min-w-[220px]">
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-stone-700">
                          ${user.used_cost.toFixed(2)} / {user.monthly_cost_limit === null ? "unlimited" : `$${user.monthly_cost_limit.toFixed(2)}`}
                        </div>
                        {user.monthly_cost_limit !== null && (
                          <div className="h-2 overflow-hidden rounded-full bg-stone-200">
                            <div
                              className={`h-full ${quotaTone(user.used_cost, user.monthly_cost_limit)}`}
                            style={{ width: `${Math.min(100, user.monthly_cost_limit > 0 ? (user.used_cost / user.monthly_cost_limit) * 100 : 0)}%` }}
                          />
                        </div>
                        )}
                        {user.close_to_cost_limit && <div className="text-xs font-medium text-amber-600">Close to cost limit</div>}
                        <div className="grid grid-cols-2 gap-2">
                          <input
                            className="w-full rounded-lg border border-stone-200 px-2 py-1"
                            type="number"
                            step="0.01"
                            value={user.monthly_cost_limit ?? ""}
                            placeholder="Unlimited"
                            onChange={(e) => setUsers((list) => list.map((item) => item.id === user.id ? { ...item, monthly_cost_limit: e.target.value === "" ? null : Number(e.target.value) } : item))}
                            onBlur={(e) => updateUser(user, { monthly_cost_limit: e.target.value === "" ? null : Number(e.target.value) })}
                          />
                          <input
                            className="w-full rounded-lg border border-stone-200 px-2 py-1"
                            type="number"
                            step="0.01"
                            value={user.used_cost}
                            onChange={(e) => setUsers((list) => list.map((item) => item.id === user.id ? { ...item, used_cost: Number(e.target.value) || 0 } : item))}
                            onBlur={(e) => updateUser(user, { used_cost: Number(e.target.value) || 0 })}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-2">
                        <Button size="sm" variant="outline" onClick={() => resetQuota(user.id)}>Reset usage</Button>
                        <Button size="sm" variant="outline" onClick={() => resetCost(user.id)}>Reset cost</Button>
                        <Button size="sm" variant="danger" onClick={() => deleteUser(user.id)}>Delete</Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </AdminShell>
  );
}
