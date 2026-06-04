"use client";

const JOB_STEPS = [
  "validating",
  "dry_run",
  "pushing_card",
  "waiting_nm_id",
  "merging_nm",
  "uploading_media",
  "completed",
];

const LABELS: Record<string, string> = {
  validating: "Validate",
  dry_run: "Dry run",
  pushing_card: "Push card",
  waiting_nm_id: "Wait NM ID",
  merging_nm: "Merge",
  uploading_media: "Upload media",
  completed: "Completed",
  failed: "Failed",
};

export function StepIndicator({
  currentStep,
  job,
}: {
  currentStep: number;
  job?: { status?: string; step?: string; error?: string | null } | null;
}) {
  const flowSteps = ["Inputs", "Analyze", "Edit Details", "Done"];
  const jobIndex = job?.step ? Math.max(0, JOB_STEPS.indexOf(job.step)) : -1;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {flowSteps.map((label, index) => (
          <div key={label} className="flex items-center gap-3">
            <span
              className={`flex h-8 w-8 items-center justify-center rounded-full border text-xs font-semibold ${
                index <= currentStep ? "border-brand bg-brand text-white shadow-soft-sm" : "border-zinc-300 bg-white text-zinc-500"
              }`}
            >
              {index + 1}
            </span>
            <span className={index <= currentStep ? "text-zinc-950" : "text-zinc-500"}>{label}</span>
            {index < flowSteps.length - 1 && <span className="h-px w-8 bg-zinc-200" />}
          </div>
        ))}
      </div>

      {job && (
        <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-soft-sm">
          <div className="mb-3 flex items-center justify-between gap-4">
            <div>
              <div className="text-sm font-semibold text-zinc-950">Background Job</div>
              <div className="text-xs text-zinc-500">
                {job.status === "failed" ? "Needs user fix" : LABELS[job.step || ""] || job.step || "Queued"}
              </div>
            </div>
            <span
              className={`rounded-full px-3 py-1 text-xs ${
                job.status === "failed"
                  ? "bg-rose-50 text-rose-700"
                  : job.status === "completed"
                    ? "bg-emerald-50 text-emerald-700"
                    : "bg-brand/10 text-brand"
              }`}
            >
              {job.status || "queued"}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-7">
            {JOB_STEPS.map((step, index) => (
              <div
                key={step}
                className={`rounded-lg border px-3 py-2 text-xs transition-all duration-300 ${
                  index <= jobIndex || job?.status === "completed"
                    ? "border-brand/60 bg-indigo-50 text-zinc-950"
                    : "border-zinc-200 bg-zinc-50 text-zinc-500"
                }`}
              >
                {LABELS[step]}
              </div>
            ))}
          </div>
          {job.error && (
            <pre className="mt-3 whitespace-pre-wrap rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
              {job.error}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
