"use client";

import Image from "next/image";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/contexts/ToastContext";
import { api, API_BASE } from "@/lib/api";

type JobAsset = {
  label?: string;
  url: string;
  model_id?: string | null;
};

type UsageRecord = {
  id: string;
  provider: string;
  model: string;
  operation: string;
  quantity: number;
  estimated_cost: number;
  created_at: string;
};

type JobDetail = {
  id: string;
  job_type: string;
  status: string;
  step: string;
  quantity: number;
  ai_model?: string | null;
  model_id?: string | null;
  prompt?: string | null;
  retry_count: number;
  estimated_cost: number;
  garment_json: Record<string, unknown>;
  validation_result: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  images: Array<Record<string, unknown> & {
    image_id?: string;
    url?: string;
    fileName?: string;
    label?: string;
    pose?: string;
    validation_result?: {
      validation_status?: "approved" | "warning" | "review_required" | "failed";
      validation_score?: number;
      risk_level?: "low" | "medium" | "high";
      warnings?: string[];
      dominant_delta_e?: number | null;
      palette_delta_e?: number | null;
      missing_details?: string[];
      retry_used?: boolean;
      can_use_for_listing?: boolean;
      pose_validation?: "pass" | "warning";
      detected_pose?: string | null;
      realism_issues?: string[];
    };
  }>;
  input_images: JobAsset[];
  selected_model_image?: JobAsset | null;
  usage_records: UsageRecord[];
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
};

function toImageUrl(url?: string | null) {
  if (!url) return null;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return `${API_BASE.replace("/api/v1", "")}${url}`;
}

function JsonCard({ title, value }: { title: string; value: unknown }) {
  return (
    <section className="rounded-[24px] border border-stone-200 bg-white p-5">
      <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-stone-500">{title}</h2>
      <pre className="mt-4 overflow-x-auto rounded-2xl bg-stone-950 p-4 text-xs leading-6 text-stone-100">
        {JSON.stringify(value, null, 2)}
      </pre>
    </section>
  );
}

export default function AdminJobDetailPage() {
  const params = useParams<{ jobId: string }>();
  const { error, success } = useToast();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadJob = async () => {
    const response = await api.get(`/admin/jobs/${params.jobId}`);
    setJob(response);
  };

  useEffect(() => {
    let active = true;
    api.get(`/admin/jobs/${params.jobId}`)
      .then((response) => {
        if (active) {
          setJob(response);
        }
      })
      .catch((err) => {
        if (active) {
          setJob(null);
          error("Load failed", err instanceof Error ? err.message : "Request failed");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [error, params.jobId]);

  const runImageAction = async (imageId: string, action: "approve" | "reject" | "retry") => {
    setActionLoading(`${imageId}:${action}`);
    try {
      if (action === "retry") {
        await api.post(`/admin/jobs/${params.jobId}/images/${imageId}/retry`);
        success("Image retry queued");
      } else {
        await api.post(`/admin/jobs/${params.jobId}/images/${imageId}/actions`, { action });
        success("Image review updated");
      }
      await loadJob();
    } catch (err) {
      error("Action failed", err instanceof Error ? err.message : "Request failed");
    } finally {
      setActionLoading(null);
    }
  };

  const badgeClass = (status?: string) => {
    if (status === "approved") return "bg-emerald-50 text-emerald-700 border-emerald-200";
    if (status === "warning") return "bg-amber-50 text-amber-700 border-amber-200";
    if (status === "review_required") return "bg-orange-50 text-orange-700 border-orange-200";
    if (status === "failed") return "bg-rose-50 text-rose-700 border-rose-200";
    return "bg-stone-100 text-stone-600 border-stone-200";
  };

  return (
    <AdminShell title={`Job ${params.jobId}`} subtitle="Inspect source assets, prompting, validation output, retries, and usage cost for a single generation job.">
      {loading ? (
        <div className="rounded-[24px] border border-stone-200 bg-white p-8 text-sm text-stone-500">Loading job details...</div>
      ) : !job ? (
        <div className="rounded-[24px] border border-rose-200 bg-rose-50 p-8 text-sm text-rose-700">Job not found.</div>
      ) : (
        <div className="space-y-6">
          <section className="rounded-[24px] border border-stone-200 bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-stone-950">{job.id}</h2>
                <p className="mt-2 text-sm text-stone-500">{job.job_type} / {job.status} / {job.step}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full bg-stone-100 px-3 py-1 text-xs uppercase tracking-[0.2em] text-stone-500">{job.ai_model || "n/a"}</span>
                <span className="rounded-full bg-stone-100 px-3 py-1 text-xs uppercase tracking-[0.2em] text-stone-500">qty {job.quantity}</span>
                <span className="rounded-full bg-stone-100 px-3 py-1 text-xs uppercase tracking-[0.2em] text-stone-500">retry {job.retry_count}</span>
                <span className="rounded-full bg-stone-100 px-3 py-1 text-xs uppercase tracking-[0.2em] text-stone-500">${job.estimated_cost.toFixed(4)}</span>
              </div>
            </div>
            {job.prompt ? (
              <div className="mt-4 rounded-2xl bg-stone-50 p-4 text-sm text-stone-700">{job.prompt}</div>
            ) : null}
            {job.error_message ? (
              <div className="mt-4 rounded-2xl bg-rose-50 p-4 text-sm text-rose-700">{job.error_message}</div>
            ) : null}
          </section>

          <section className="grid gap-6 xl:grid-cols-3">
            <div className="rounded-[24px] border border-stone-200 bg-white p-5 xl:col-span-2">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold text-stone-950">Generated outputs</h2>
                <span className="text-sm text-stone-500">{job.images.length} image(s)</span>
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                {job.images.map((image, index) => {
                  const imageUrl = toImageUrl(image.url);
                  return imageUrl ? (
                    <div key={image.image_id || image.url || index} className="overflow-hidden rounded-2xl border border-stone-200">
                      <Image src={imageUrl} alt={`Generated output ${index + 1}`} width={1024} height={1024} className="h-72 w-full object-cover" />
                      <div className="space-y-3 border-t border-stone-200 p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${badgeClass(image.validation_result?.validation_status)}`}>
                            {image.validation_result?.validation_status === "failed" ? "High Risk" : image.validation_result?.validation_status === "review_required" ? "Review Required" : image.validation_result?.validation_status === "warning" ? "Warning" : "Approved"}
                          </span>
                          <span className="text-xs text-stone-500">{image.label || `Image ${index + 1}`}</span>
                          <span className="text-xs text-stone-500">score {image.validation_result?.validation_score ?? "n/a"}</span>
                          <span className="text-xs text-stone-500">risk {image.validation_result?.risk_level || "n/a"}</span>
                        </div>
                        {image.validation_result?.validation_status === "failed" ? (
                          <div className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">High risk: not recommended for publishing.</div>
                        ) : null}
                        <div className="grid gap-1 text-xs text-stone-600">
                          <div>Dominant DeltaE: {typeof image.validation_result?.dominant_delta_e === "number" ? image.validation_result.dominant_delta_e.toFixed(1) : "n/a"}</div>
                          <div>Palette DeltaE: {typeof image.validation_result?.palette_delta_e === "number" ? image.validation_result.palette_delta_e.toFixed(1) : "n/a"}</div>
                          <div>Retry used: {image.validation_result?.retry_used ? "Yes" : "No"}</div>
                          <div>Pose validation: {image.validation_result?.pose_validation === "warning" ? "Warning" : "Pass"}</div>
                          <div>Detected pose: {image.validation_result?.detected_pose || "n/a"}</div>
                          {image.validation_result?.missing_details?.length ? <div>Missing details: {image.validation_result.missing_details.join(", ")}</div> : null}
                          {image.validation_result?.realism_issues?.length ? <div>Realism notes: {image.validation_result.realism_issues.join(", ")}</div> : null}
                        </div>
                        {image.validation_result?.warnings?.length ? (
                          <div className="space-y-1">
                            {image.validation_result.warnings.map((warning, warningIndex) => (
                              <div key={`${warning}-${warningIndex}`} className="rounded-xl bg-stone-50 px-3 py-2 text-xs text-stone-700">{warning}</div>
                            ))}
                          </div>
                        ) : null}
                        {image.image_id ? (
                          <div className="flex flex-wrap gap-2">
                            <Button size="sm" variant="outline" onClick={() => void runImageAction(image.image_id!, "approve")} isLoading={actionLoading === `${image.image_id}:approve`}>
                              Approve
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => void runImageAction(image.image_id!, "reject")} isLoading={actionLoading === `${image.image_id}:reject`}>
                              Reject
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => void runImageAction(image.image_id!, "retry")} isLoading={actionLoading === `${image.image_id}:retry`}>
                              Retry image
                            </Button>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ) : null;
                })}
              </div>
            </div>

            <div className="rounded-[24px] border border-stone-200 bg-white p-5">
              <h2 className="text-lg font-semibold text-stone-950">Selected model</h2>
              {job.selected_model_image?.url ? (
                <div className="mt-4 overflow-hidden rounded-2xl border border-stone-200">
                  <Image
                    src={toImageUrl(job.selected_model_image.url) || ""}
                    alt={job.selected_model_image.model_id || "Selected model"}
                    width={720}
                    height={960}
                    className="h-80 w-full object-cover"
                  />
                </div>
              ) : (
                <div className="mt-4 rounded-2xl bg-stone-100 p-6 text-sm text-stone-500">No model reference saved for this job.</div>
              )}
              <p className="mt-3 text-sm text-stone-500">Model ID: {job.selected_model_image?.model_id || job.model_id || "n/a"}</p>
            </div>
          </section>

          <section className="rounded-[24px] border border-stone-200 bg-white p-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-stone-950">Uploaded inputs</h2>
              <Button size="sm" variant="outline" onClick={() => window.location.reload()}>Refresh</Button>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              {job.input_images.map((image) => (
                <article key={image.label || image.url} className="overflow-hidden rounded-2xl border border-stone-200">
                  <Image src={toImageUrl(image.url) || ""} alt={image.label || "Input image"} width={720} height={960} className="h-64 w-full object-cover" />
                  <div className="border-t border-stone-200 px-4 py-3 text-sm font-medium text-stone-700">{image.label || "input"}</div>
                </article>
              ))}
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-2">
            <JsonCard title="Garment JSON" value={job.garment_json} />
            <JsonCard title="Validation Result" value={job.validation_result} />
            <JsonCard title="Retry Metadata" value={job.metadata_json} />
            <section className="rounded-[24px] border border-stone-200 bg-white p-5">
              <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-stone-500">Usage And Cost</h2>
              <div className="mt-4 space-y-3">
                {job.usage_records.length ? job.usage_records.map((record) => (
                  <div key={record.id} className="rounded-2xl border border-stone-200 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="font-medium text-stone-950">{record.provider} / {record.model}</div>
                        <div className="mt-1 text-sm text-stone-500">{record.operation} / qty {record.quantity}</div>
                      </div>
                      <div className="text-sm font-medium text-stone-950">${record.estimated_cost.toFixed(4)}</div>
                    </div>
                  </div>
                )) : (
                  <div className="rounded-2xl bg-stone-50 p-4 text-sm text-stone-500">No usage records stored for this job.</div>
                )}
              </div>
            </section>
          </section>
        </div>
      )}
    </AdminShell>
  );
}
