import React from "react";
import { CheckCircle, XCircle, AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { formatDatetime, formatRetryAfter } from "@/lib/finance-utils";
import type { FinanceSystemStatus, ApiStatusBlock } from "@/lib/types/finance";
import { cn } from "@/lib/utils";

interface FinanceSystemStatusCardProps {
  status: FinanceSystemStatus | null;
  isLoading: boolean;
  onRefresh: () => void;
}

function ApiStatusRow({ label, block }: { label: string; block: ApiStatusBlock }) {
  const ok = block.available && !block.inCooldown;
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-zinc-600">{label}</span>
      <div className="flex items-center gap-2">
        {block.inCooldown && block.cooldowns[0] && (
          <span className="text-xs text-amber-600">
            retry in {formatRetryAfter(block.cooldowns[0].retryAfterSeconds)}
          </span>
        )}
        {ok ? (
          <CheckCircle size={15} className="text-green-500" />
        ) : block.inCooldown ? (
          <AlertTriangle size={15} className="text-amber-500" />
        ) : (
          <XCircle size={15} className="text-red-500" />
        )}
      </div>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div className="flex items-center justify-between py-1.5">
      <div className="shimmer h-4 w-28 rounded" />
      <div className="shimmer h-4 w-12 rounded" />
    </div>
  );
}

export function FinanceSystemStatusCard({
  status,
  isLoading,
  onRefresh,
}: FinanceSystemStatusCardProps) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-soft-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-950">System Status</h2>
        <Button
          variant="ghost"
          size="icon"
          onClick={onRefresh}
          isLoading={isLoading}
          title="Refresh status"
        >
          <RefreshCw size={14} />
        </Button>
      </div>

      {isLoading && !status ? (
        <div className="divide-y divide-zinc-100">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonRow key={i} />
          ))}
        </div>
      ) : status ? (
        <>
          <div className="divide-y divide-zinc-100">
            <ApiStatusRow label="Content API" block={status.contentApi} />
            <ApiStatusRow label="Finance API" block={status.financeApi} />
            <ApiStatusRow label="Common API" block={status.commonApi} />
            <ApiStatusRow label="Seller Info API" block={status.sellerInfoApi} />
          </div>

          <div className="mt-4 space-y-1.5 border-t border-zinc-100 pt-4">
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">Bootstrap sync</span>
              <span className="font-medium text-zinc-700">
                {status.bootstrapStatus ?? "idle"}
              </span>
            </div>
            {(status.bootstrapRangeFrom || status.bootstrapRangeTo) && (
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-500">Bootstrap range</span>
                <span className="font-medium text-zinc-700">
                  {status.bootstrapRangeFrom ?? "—"} → {status.bootstrapRangeTo ?? "—"}
                </span>
              </div>
            )}
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">Last product sync</span>
              <span className="font-medium text-zinc-700">
                {formatDatetime(status.lastSuccessfulProductSyncAt)}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">Last finance sync</span>
              <span className="font-medium text-zinc-700">
                {formatDatetime(status.lastSuccessfulFinanceSyncAt)}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">Last daily auto sync</span>
              <span className="font-medium text-zinc-700">
                {status.lastSuccessfulDailySyncDate ?? "—"}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">Daily auto-sync status</span>
              <span className="font-medium text-zinc-700">
                {status.lastDailySyncStatus ?? "idle"}
              </span>
            </div>
            {status.nextScheduledRunAt && (
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-500">Next scheduled run</span>
                <span className="font-medium text-zinc-700">
                  {formatDatetime(status.nextScheduledRunAt)}
                </span>
              </div>
            )}
            {status.lastFailedSyncAt && (
              <div className="flex items-center justify-between text-xs">
                <span className="text-red-500">Last failed sync</span>
                <span className="font-medium text-red-600">
                  {formatDatetime(status.lastFailedSyncAt)}
                </span>
              </div>
            )}
            {status.lastFailedSyncError && (
              <p className="mt-1 truncate rounded bg-red-50 px-2 py-1 text-xs text-red-600">
                {status.lastFailedSyncError}
              </p>
            )}
            {status.lastDailySyncError && (
              <p className="mt-1 truncate rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">
                {status.lastDailySyncError}
              </p>
            )}
          </div>

          <div className="mt-4 space-y-1.5 border-t border-zinc-100 pt-4">
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">Gemini AI</span>
              <span
                className={cn(
                  "font-medium",
                  status.geminiConfigured ? "text-green-600" : "text-zinc-400"
                )}
              >
                {status.geminiConfigured ? "Enabled" : "Disabled"}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">Missing cost settings</span>
              <span
                className={cn(
                  "font-medium",
                  status.hasProductsMissingFinanceSettings
                    ? "text-amber-600"
                    : "text-green-600"
                )}
              >
                {status.missingFinanceSettingsCount} products
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">Unmapped finance rows</span>
              <span
                className={cn(
                  "font-medium",
                  status.hasUnmappedFinanceRows ? "text-amber-600" : "text-green-600"
                )}
              >
                {status.unmappedFinanceRowsCount} rows
              </span>
            </div>
          </div>
        </>
      ) : (
        <p className="py-4 text-center text-sm text-zinc-400">Status unavailable</p>
      )}
    </div>
  );
}
