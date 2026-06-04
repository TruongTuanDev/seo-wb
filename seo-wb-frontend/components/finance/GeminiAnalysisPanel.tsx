"use client";

import React, { useState } from "react";
import { Sparkles, ChevronDown, ChevronUp, Clock } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/finance-utils";
import { financeApi } from "@/lib/finance-api";
import { useToast } from "@/contexts/ToastContext";
import type { GeminiFinanceAnalysis, GeminiSnapshotItem, GroupBy } from "@/lib/types/finance";

interface GeminiAnalysisPanelProps {
  storeId: number;
  dateFrom: string;
  dateTo: string;
  groupBy: GroupBy;
  geminiConfigured: boolean;
  snapshots: GeminiSnapshotItem[];
  onSnapshotsRefresh: () => void;
}

export function GeminiAnalysisPanel({
  storeId,
  dateFrom,
  dateTo,
  groupBy,
  geminiConfigured,
  snapshots,
  onSnapshotsRefresh,
}: GeminiAnalysisPanelProps) {
  const { success, error } = useToast();
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [latestAnalysis, setLatestAnalysis] = useState<GeminiFinanceAnalysis | null>(null);
  const [expandedSnapshot, setExpandedSnapshot] = useState<number | null>(null);

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    try {
      const result = await financeApi.analyzeWithGemini(storeId, {
        date_from: dateFrom,
        date_to: dateTo,
        group_by: groupBy,
      });
      setLatestAnalysis(result);
      success("Analysis complete", "Gemini analysis generated successfully.");
      onSnapshotsRefresh();
    } catch (err) {
      error("Analysis failed", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (!geminiConfigured) {
    return (
      <div className="rounded-xl border border-dashed border-zinc-200 bg-zinc-50 p-6 text-center">
        <Sparkles size={24} className="mx-auto mb-2 text-zinc-300" />
        <p className="text-sm font-medium text-zinc-500">Gemini AI is not configured</p>
        <p className="mt-1 text-xs text-zinc-400">
          Add a Gemini API key to your backend configuration to enable AI-powered finance analysis.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-ai-accent" />
          <span className="text-sm font-semibold text-zinc-950">Gemini AI Analysis</span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleAnalyze}
          isLoading={isAnalyzing}
          disabled={isAnalyzing}
        >
          <Sparkles size={13} className="mr-1.5" />
          Analyze Period
        </Button>
      </div>

      {/* Latest analysis result */}
      {latestAnalysis && (
        <div className="rounded-xl border border-purple-200 bg-purple-50 p-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-purple-500">
            Latest Analysis
          </p>
          <p className="whitespace-pre-wrap text-sm text-zinc-700">
            {latestAnalysis.analysis.summary}
          </p>
        </div>
      )}

      {/* Snapshot history */}
      {snapshots.length > 0 && (
        <div className="rounded-xl border border-zinc-200 bg-white">
          <div className="border-b border-zinc-100 px-4 py-3">
            <p className="text-xs font-semibold text-zinc-500">Analysis History</p>
          </div>
          <ul className="divide-y divide-zinc-100">
            {snapshots.slice(0, 5).map((snap) => (
              <li key={snap.id} className="px-4 py-3">
                <button
                  className="flex w-full items-center justify-between text-left"
                  onClick={() =>
                    setExpandedSnapshot(expandedSnapshot === snap.id ? null : snap.id)
                  }
                >
                  <div className="flex items-center gap-2">
                    <Clock size={13} className="text-zinc-400" />
                    <span className="text-sm text-zinc-700">
                      {formatDate(snap.dateFrom)} — {formatDate(snap.dateTo)}
                    </span>
                  </div>
                  {expandedSnapshot === snap.id ? (
                    <ChevronUp size={14} className="text-zinc-400" />
                  ) : (
                    <ChevronDown size={14} className="text-zinc-400" />
                  )}
                </button>
                {expandedSnapshot === snap.id && snap.aiAnalysis?.summary && (
                  <p className="mt-2 whitespace-pre-wrap text-xs text-zinc-600">
                    {snap.aiAnalysis.summary}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {snapshots.length === 0 && !latestAnalysis && (
        <p className="text-center text-sm text-zinc-400">
          No analysis snapshots yet. Click Analyze Period to generate one.
        </p>
      )}
    </div>
  );
}
