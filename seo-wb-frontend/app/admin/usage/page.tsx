"use client";

import { useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminStatCard } from "@/components/admin/AdminStatCard";
import { api } from "@/lib/api";

type UsageSummary = {
  total_estimated_cost: number;
  total_quantity: number;
  successful_generations: number;
  failed_generations: number;
  by_provider: Record<string, number>;
  items: Array<{ id: string; provider: string; model: string; quantity: number; estimated_cost: number }>;
};

export default function AdminUsagePage() {
  const [data, setData] = useState<UsageSummary | null>(null);

  useEffect(() => {
    api.get("/admin/usage").then(setData).catch(() => setData(null));
  }, []);

  return (
    <AdminShell title="Usage" subtitle="Provider-level cost and throughput tracking derived from completed generation jobs.">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <AdminStatCard label="Estimated cost" value={`$${(data?.total_estimated_cost ?? 0).toFixed(2)}`} />
        <AdminStatCard label="Image quantity" value={String(data?.total_quantity ?? 0)} />
        <AdminStatCard label="Successful generations" value={String(data?.successful_generations ?? 0)} />
        <AdminStatCard label="Failed generations" value={String(data?.failed_generations ?? 0)} />
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
        <section className="rounded-[24px] border border-stone-200 bg-stone-50/80 p-5">
          <h3 className="text-lg font-semibold text-stone-950">By provider</h3>
          <div className="mt-4 space-y-3">
            {Object.entries(data?.by_provider || {}).map(([provider, cost]) => (
              <div key={provider} className="flex items-center justify-between rounded-2xl bg-white px-4 py-3">
                <span className="capitalize text-stone-600">{provider}</span>
                <span className="font-semibold text-stone-950">${cost.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </section>
        <section className="overflow-x-auto rounded-[24px] border border-stone-200">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-stone-50 text-stone-500">
              <tr>
                <th className="px-4 py-3">Record</th>
                <th className="px-4 py-3">Provider</th>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3">Quantity</th>
                <th className="px-4 py-3">Cost</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items || []).map((item) => (
                <tr key={item.id} className="border-t border-stone-200">
                  <td className="px-4 py-3 font-medium text-stone-950">{item.id}</td>
                  <td className="px-4 py-3 capitalize">{item.provider}</td>
                  <td className="px-4 py-3">{item.model}</td>
                  <td className="px-4 py-3">{item.quantity}</td>
                  <td className="px-4 py-3">${item.estimated_cost.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </AdminShell>
  );
}
