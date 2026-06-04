export function AdminStatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-[24px] border border-stone-200 bg-stone-50/80 p-5">
      <p className="text-xs uppercase tracking-[0.24em] text-stone-400">{label}</p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">{value}</p>
      {hint ? <p className="mt-2 text-sm text-stone-500">{hint}</p> : null}
    </div>
  );
}
