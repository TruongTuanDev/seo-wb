"use client";

import { useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminStatCard } from "@/components/admin/AdminStatCard";
import { api } from "@/lib/api";

type Dashboard = {
  total_users: number;
  total_models: number;
  total_generated_images: number;
  total_failed_jobs: number;
  total_api_cost_estimate: number;
  images_generated_today: number;
  validation_failed_count: number;
  active_users: number;
  users_over_quota_80: number;
  users_over_cost_80: number;
  users_over_quota: number;
  users_over_cost: number;
  top_usage_users: DashboardUserMetric[];
  top_cost_users: DashboardUserMetric[];
};

type DashboardUserMetric = {
  user_id: number;
  name: string;
  email: string;
  plan_type: string;
  used_quota: number;
  monthly_quota: number;
  quota_percent: number;
  used_cost: number;
  monthly_cost_limit: number | null;
  cost_percent: number | null;
};

export default function AdminDashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [plan, setPlan] = useState("");
  const [status, setStatus] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (plan) params.set("plan", plan);
    if (status) params.set("status", status);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    const query = params.toString();
    api.get(`/admin${query ? `?${query}` : ""}`).then(setData).catch(() => setData(null));
  }, [plan, status, dateFrom, dateTo]);

  return (
    <AdminShell title="Dashboard" subtitle="Operational visibility across users, templates, generation throughput, and estimated API spend.">
      <div className="mb-6 grid gap-3 rounded-[24px] border border-stone-200 bg-stone-50/80 p-5 md:grid-cols-4">
        <label className="text-sm font-medium text-stone-700">
          Plan
          <select className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm" value={plan} onChange={(e) => setPlan(e.target.value)}>
            <option value="">All</option>
            <option value="free">Free</option>
            <option value="pro">Pro</option>
            <option value="agency">Agency</option>
          </select>
        </label>
        <label className="text-sm font-medium text-stone-700">
          Status
          <select className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            <option value="active">active</option>
            <option value="suspended">suspended</option>
          </select>
        </label>
        <label className="text-sm font-medium text-stone-700">
          Date from
          <input className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label className="text-sm font-medium text-stone-700">
          Date to
          <input className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <AdminStatCard label="Total users" value={String(data?.total_users ?? 0)} />
        <AdminStatCard label="Total models" value={String(data?.total_models ?? 0)} />
        <AdminStatCard label="Generated images" value={String(data?.total_generated_images ?? 0)} />
        <AdminStatCard label="Failed jobs" value={String(data?.total_failed_jobs ?? 0)} />
        <AdminStatCard label="API cost estimate" value={`$${(data?.total_api_cost_estimate ?? 0).toFixed(2)}`} />
        <AdminStatCard label="Images today" value={String(data?.images_generated_today ?? 0)} />
        <AdminStatCard label="Validation failures" value={String(data?.validation_failed_count ?? 0)} />
        <AdminStatCard label="Active users" value={String(data?.active_users ?? 0)} />
        <AdminStatCard label="Users over 80% quota" value={String(data?.users_over_quota_80 ?? 0)} />
        <AdminStatCard label="Users over 80% cost" value={String(data?.users_over_cost_80 ?? 0)} />
        <AdminStatCard label="Users over quota" value={String(data?.users_over_quota ?? 0)} />
        <AdminStatCard label="Users over cost" value={String(data?.users_over_cost ?? 0)} />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <section className="rounded-[24px] border border-stone-200 bg-white p-5">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-stone-950">Top usage users</h2>
            <p className="text-sm text-stone-500">Accounts closest to their image quota this cycle.</p>
          </div>
          <div className="space-y-3">
            {(data?.top_usage_users ?? []).map((item) => (
              <div key={`quota-${item.user_id}`} className="rounded-2xl border border-stone-200 bg-stone-50/70 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium text-stone-950">{item.name}</div>
                    <div className="text-sm text-stone-500">{item.email}</div>
                  </div>
                  <span className="rounded-full bg-stone-900 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-white">
                    {item.plan_type}
                  </span>
                </div>
                <div className="mt-3 flex items-center justify-between text-sm text-stone-700">
                  <span>{item.used_quota} / {item.monthly_quota} images</span>
                  <span>{item.quota_percent.toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-[24px] border border-stone-200 bg-white p-5">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-stone-950">Top cost users</h2>
            <p className="text-sm text-stone-500">Accounts with the highest estimated AI cost consumption.</p>
          </div>
          <div className="space-y-3">
            {(data?.top_cost_users ?? []).map((item) => (
              <div key={`cost-${item.user_id}`} className="rounded-2xl border border-stone-200 bg-stone-50/70 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium text-stone-950">{item.name}</div>
                    <div className="text-sm text-stone-500">{item.email}</div>
                  </div>
                  <span className="rounded-full bg-stone-900 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-white">
                    {item.plan_type}
                  </span>
                </div>
                <div className="mt-3 flex items-center justify-between text-sm text-stone-700">
                  <span>
                    ${item.used_cost.toFixed(2)} / {item.monthly_cost_limit === null ? "Unlimited" : `$${item.monthly_cost_limit.toFixed(2)}`}
                  </span>
                  <span>{item.cost_percent === null ? "No cap" : `${item.cost_percent.toFixed(0)}%`}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </AdminShell>
  );
}
