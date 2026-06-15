"use client";

import { startTransition, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { AdminShell } from "@/components/admin/AdminShell";
import { useToast } from "@/contexts/ToastContext";
import { api } from "@/lib/api";
import { PLAN_OPTIONS, planByCode, planLabel } from "@/lib/plans";

type AdminUser = {
  id: number;
  name: string;
  email: string;
  role: string;
  status: string;
  plan_type: string;
  max_images_per_job: number;
  allow_gpt_image: boolean;
  priority_queue: boolean;
  monthly_quota: number;
  used_quota: number;
  credit_balance: number;
  credits_used: number;
  credits_granted: number;
  remaining_cards: number;
  remaining_images: number;
  quota_reset_at: string | null;
  close_to_quota_limit: boolean;
};

type GrantForm = {
  cards: string;
  images: string;
};

const emptyForm = {
  name: "",
  email: "",
  password: "",
  role: "user",
  plan_type: "free",
  monthly_quota: "3",
};

export default function AdminUsersPage() {
  const { success, error } = useToast();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [grants, setGrants] = useState<Record<number, GrantForm>>({});
  const [loadingUserId, setLoadingUserId] = useState<number | null>(null);

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
        monthly_cost_limit: null,
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

  const assignPlan = async (user: AdminUser, planType: string) => {
    const plan = planByCode(planType);
    try {
      setLoadingUserId(user.id);
      await api.put(`/admin/users/${user.id}`, { plan_type: plan.value });
      await load();
      success("Plan added", `+${plan.cards} thẻ và +${plan.images} ảnh đã được cộng vào số dư hiện tại.`);
    } catch (err) {
      error("Plan update failed", err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoadingUserId(null);
    }
  };

  const grantQuota = async (user: AdminUser) => {
    const current = grants[user.id] || { cards: "", images: "" };
    const cards = Number(current.cards) || 0;
    const images = Number(current.images) || 0;
    try {
      setLoadingUserId(user.id);
      await api.post(`/admin/users/${user.id}/grant-quota`, {
        card_quota_delta: cards,
        image_credit_delta: images,
        note: "Manual admin top-up",
      });
      setGrants((state) => ({ ...state, [user.id]: { cards: "", images: "" } }));
      await load();
      success("Quota added", `+${cards} thẻ, +${images} ảnh`);
    } catch (err) {
      error("Grant failed", err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoadingUserId(null);
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

  const deleteUser = async (userId: number) => {
    try {
      await api.delete(`/admin/users/${userId}`);
      await load();
      success("User deleted");
    } catch (err) {
      error("Delete failed", err instanceof Error ? err.message : "Request failed");
    }
  };

  const quotaTone = (remaining: number) => {
    if (remaining <= 0) return "text-rose-600 bg-rose-50 border-rose-200";
    if (remaining <= 2) return "text-amber-700 bg-amber-50 border-amber-200";
    return "text-emerald-700 bg-emerald-50 border-emerald-200";
  };

  const formatDate = (value: string | null) => {
    if (!value) return "Not scheduled";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString();
  };

  const handlePlanChange = (planType: string) => {
    const plan = planByCode(planType);
    setForm((state) => ({
      ...state,
      plan_type: plan.value,
      monthly_quota: String(plan.cards),
    }));
  };

  return (
    <AdminShell title="Users" subtitle="Cấp gói, cộng thêm thẻ và ảnh sau khi khách chuyển tiền. Gói mới luôn cộng dồn vào số dư cũ.">
      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
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
                  <option key={plan.value} value={plan.value}>
                    {plan.label} - {plan.cards} thẻ / {plan.images} ảnh
                  </option>
                ))}
              </select>
            </label>
            <Input label="Card quota" type="number" value={form.monthly_quota} onChange={(e) => setForm((s) => ({ ...s, monthly_quota: e.target.value }))} />
            <Button variant="brand" className="w-full" onClick={createUser}>Create user</Button>
          </div>

          <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-4">
            <p className="text-sm font-semibold text-stone-900">Active plans</p>
            <div className="mt-3 space-y-2">
              {PLAN_OPTIONS.map((plan) => (
                <div key={plan.value} className="rounded-xl bg-stone-50 px-3 py-2 text-xs text-stone-600">
                  <div className="font-semibold text-stone-900">{plan.label}: {plan.priceRub.toLocaleString("ru-RU")} ₽</div>
                  <div>{plan.cards} thẻ, {plan.images} ảnh</div>
                </div>
              ))}
            </div>
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
                  <th className="px-4 py-3">Role / Status</th>
                  <th className="px-4 py-3">Plan</th>
                  <th className="px-4 py-3">Số dư</th>
                  <th className="px-4 py-3">Cộng thêm</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => {
                  const grant = grants[user.id] || { cards: "", images: "" };
                  return (
                    <tr key={user.id} className="border-t border-stone-200 align-top">
                      <td className="px-4 py-3">
                        <div className="font-medium text-stone-950">{user.name}</div>
                        <div className="text-stone-500">{user.email}</div>
                        <div className="mt-1 text-xs text-stone-400">Next reset: {formatDate(user.quota_reset_at)}</div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="space-y-2">
                          <input className="w-28 rounded-lg border border-stone-200 px-2 py-1" value={user.role} onChange={(e) => setUsers((list) => list.map((item) => item.id === user.id ? { ...item, role: e.target.value } : item))} onBlur={(e) => updateUser(user, { role: e.target.value })} />
                          <select className="w-28 rounded-lg border border-stone-200 px-2 py-1" value={user.status} onChange={(e) => updateUser(user, { status: e.target.value })}>
                            <option value="active">active</option>
                            <option value="suspended">suspended</option>
                          </select>
                        </div>
                      </td>
                      <td className="px-4 py-3 min-w-[220px]">
                        <select className="w-full rounded-lg border border-stone-200 px-2 py-1" value={planByCode(user.plan_type).value} onChange={(e) => void assignPlan(user, e.target.value)} disabled={loadingUserId === user.id}>
                          {PLAN_OPTIONS.map((plan) => (
                            <option key={plan.value} value={plan.value}>{plan.label}</option>
                          ))}
                        </select>
                        <p className="mt-2 text-xs text-stone-500">
                          Current: {planLabel(user.plan_type)}. Chọn gói ở đây sẽ cộng thêm quota gói vào số dư hiện tại.
                        </p>
                        <p className="mt-1 text-xs text-stone-500">
                          Max/job: {user.max_images_per_job} · GPT: {user.allow_gpt_image ? "on" : "off"} · Priority: {user.priority_queue ? "yes" : "no"}
                        </p>
                      </td>
                      <td className="px-4 py-3 min-w-[240px]">
                        <div className="grid gap-2">
                          <div className={`rounded-2xl border px-3 py-2 ${quotaTone(user.remaining_cards)}`}>
                            <div className="text-xs uppercase tracking-wide opacity-75">Thẻ còn lại</div>
                            <div className="text-xl font-semibold">{user.remaining_cards}</div>
                            <div className="text-xs">Đã dùng {user.used_quota} / tổng {user.monthly_quota}</div>
                          </div>
                          <div className={`rounded-2xl border px-3 py-2 ${quotaTone(user.remaining_images)}`}>
                            <div className="text-xs uppercase tracking-wide opacity-75">Ảnh còn lại</div>
                            <div className="text-xl font-semibold">{user.remaining_images}</div>
                            <div className="text-xs">Đã dùng {user.credits_used} / đã cấp {user.credits_granted}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 min-w-[220px]">
                        <div className="grid grid-cols-2 gap-2">
                          <Input
                            label="+ thẻ"
                            type="number"
                            min="0"
                            value={grant.cards}
                            onChange={(e) => setGrants((state) => ({ ...state, [user.id]: { ...grant, cards: e.target.value } }))}
                          />
                          <Input
                            label="+ ảnh"
                            type="number"
                            min="0"
                            value={grant.images}
                            onChange={(e) => setGrants((state) => ({ ...state, [user.id]: { ...grant, images: e.target.value } }))}
                          />
                        </div>
                        <Button size="sm" variant="brand" className="mt-2 w-full" onClick={() => void grantQuota(user)} isLoading={loadingUserId === user.id}>
                          Cộng vào số dư
                        </Button>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col gap-2">
                          <Button size="sm" variant="outline" onClick={() => resetQuota(user.id)}>Reset cycle</Button>
                          <Button size="sm" variant="danger" onClick={() => deleteUser(user.id)}>Delete</Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </AdminShell>
  );
}
