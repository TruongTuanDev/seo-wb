"use client";

import Link from "next/link";
import { startTransition, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { AdminShell } from "@/components/admin/AdminShell";
import { useToast } from "@/contexts/ToastContext";
import { api } from "@/lib/api";

type Job = {
  id: string;
  user_id: number;
  job_type: string;
  status: string;
  ai_model?: string | null;
  quantity: number;
  error_message?: string | null;
  validation_result: {
    failed_validations?: Array<{ failed_reason?: string }>;
    validation_summary?: {
      approved_count?: number;
      warning_count?: number;
      review_required_count?: number;
      failed_count?: number;
    };
    seller_warning?: string | null;
  };
};

export default function AdminJobsPage() {
  const { success, error } = useToast();
  const [jobs, setJobs] = useState<Job[]>([]);

  const load = async () => setJobs(await api.get("/admin/jobs"));

  useEffect(() => {
    api.get("/admin/jobs")
      .then((response) => {
        startTransition(() => setJobs(response));
      })
      .catch(() => {
        startTransition(() => setJobs([]));
      });
  }, []);

  const retryJob = async (jobId: string) => {
    try {
      await api.post(`/admin/jobs/${jobId}/retry`);
      await load();
      success("Job requeued");
    } catch (err) {
      error("Retry failed", err instanceof Error ? err.message : "Request failed");
    }
  };

  const deleteJob = async (jobId: string) => {
    try {
      await api.delete(`/admin/jobs/${jobId}`);
      await load();
      success("Job deleted");
    } catch (err) {
      error("Delete failed", err instanceof Error ? err.message : "Request failed");
    }
  };

  return (
    <AdminShell title="Jobs" subtitle="Inspect generated image jobs, failed validations, model usage, and recovery actions from one table.">
      <div className="overflow-x-auto rounded-[24px] border border-stone-200">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-stone-50 text-stone-500">
            <tr>
              <th className="px-4 py-3">Job</th>
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Model</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Validation</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id} className="border-t border-stone-200 align-top">
                <td className="px-4 py-3">
                  <div className="font-medium text-stone-950">{job.id}</div>
                  <div className="text-stone-500">{job.job_type} / qty {job.quantity}</div>
                  <Link href={`/admin/jobs/${job.id}`} className="mt-2 inline-block text-xs font-medium text-brand hover:text-brand-hover">
                    View details
                  </Link>
                </td>
                <td className="px-4 py-3">{job.user_id}</td>
                <td className="px-4 py-3">{job.ai_model || "n/a"}</td>
                <td className="px-4 py-3">
                  <div className="font-medium text-stone-950">{job.status}</div>
                  {job.error_message ? <div className="mt-1 max-w-sm text-xs text-rose-600">{job.error_message}</div> : null}
                </td>
                <td className="px-4 py-3 text-stone-500">
                  <div>A {job.validation_result?.validation_summary?.approved_count || 0}</div>
                  <div>W {job.validation_result?.validation_summary?.warning_count || 0}</div>
                  <div>R {job.validation_result?.validation_summary?.review_required_count || 0}</div>
                  <div>F {job.validation_result?.validation_summary?.failed_count || 0}</div>
                  {job.validation_result?.seller_warning ? <div className="mt-1 max-w-xs text-xs text-amber-700">{job.validation_result.seller_warning}</div> : null}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => retryJob(job.id)}>Retry</Button>
                    <Button size="sm" variant="danger" onClick={() => deleteJob(job.id)}>Delete</Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AdminShell>
  );
}
