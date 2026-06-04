import React from "react";
import { cn } from "@/lib/utils";
import type { SyncStatus } from "@/lib/types/finance";
import { syncStatusLabel } from "@/lib/finance-utils";

interface SyncStatusBadgeProps {
  status: SyncStatus | null | undefined;
  className?: string;
}

export function SyncStatusBadge({ status, className }: SyncStatusBadgeProps) {
  if (!status) return null;

  const colorMap: Record<string, string> = {
    idle: "bg-zinc-100 text-zinc-600",
    running: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
    rate_limited: "bg-amber-100 text-amber-700",
  };

  const dotMap: Record<string, string> = {
    idle: "bg-zinc-400",
    running: "bg-blue-500 animate-pulse",
    completed: "bg-green-500",
    failed: "bg-red-500",
    rate_limited: "bg-amber-500",
  };

  const colorClass = colorMap[status] ?? "bg-zinc-100 text-zinc-600";
  const dotClass = dotMap[status] ?? "bg-zinc-400";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        colorClass,
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", dotClass)} />
      {syncStatusLabel(status)}
    </span>
  );
}
