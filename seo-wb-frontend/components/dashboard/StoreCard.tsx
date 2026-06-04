"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Store, Activity, AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import Link from "next/link";

interface StoreCardProps {
  store: {
    id: number;
    name: string;
  };
}

export function StoreCard({ store }: StoreCardProps) {
  const [limits, setLimits] = useState<{ freeLimits: number } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getErrorMessage = (err: unknown) => {
    if (err instanceof Error) return err.message;
    if (typeof err === "string") return err;
    return "Failed to fetch limits";
  };

  const fetchLimits = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.get(`/wb/card-limits?store_id=${store.id}`);
      // Usually WB returns an object with freeLimits
      setLimits(data);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [store.id]);

  useEffect(() => {
    queueMicrotask(() => {
      void fetchLimits();
    });
  }, [fetchLimits]);

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-zinc-300/80 bg-white/96 shadow-[0_12px_30px_rgba(15,23,42,0.08)] ring-1 ring-white/70 transition-all duration-200 hover:-translate-y-0.5 hover:border-zinc-400 hover:shadow-[0_18px_40px_rgba(15,23,42,0.12)]">
      <div className="p-5 flex-1">
        <div className="mb-4 flex min-w-0 items-start justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <div className="shrink-0 rounded-xl bg-gradient-to-br from-indigo-50 to-fuchsia-50 p-2.5 text-brand ring-1 ring-indigo-100">
              <Store size={22} />
            </div>
            <div className="min-w-0">
              <h3 className="truncate text-lg font-semibold text-zinc-950">{store.name}</h3>
              <p className="font-mono text-xs text-zinc-500">ID: {store.id}</p>
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-xl border border-zinc-200 bg-zinc-50/90 p-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className="flex items-center gap-2 text-sm font-medium text-zinc-700">
              <Activity size={14} className="text-zinc-500" /> API Status
            </h4>
            <button 
              onClick={fetchLimits} 
              disabled={isLoading}
              className="rounded-md p-1 text-zinc-500 transition-colors duration-150 hover:bg-white hover:text-zinc-900 disabled:opacity-50"
            >
              <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
            </button>
          </div>
          
          {isLoading && !limits && !error && (
            <div className="h-6 flex items-center">
              <div className="h-2 w-24 rounded shimmer"></div>
            </div>
          )}
          
          {error && (
            <div className="mt-2 flex items-start gap-2 text-xs text-rose-500">
              <AlertCircle size={14} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
          
          {limits && !error && (
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-semibold text-zinc-950">
                {limits.freeLimits !== undefined ? limits.freeLimits : "—"}
              </span>
              <span className="text-xs text-zinc-400 uppercase tracking-wider">Cards Remaining</span>
            </div>
          )}
        </div>
      </div>
      
      <div className="flex flex-col gap-2 border-t border-zinc-200 bg-gradient-to-r from-zinc-50 to-white p-4 sm:flex-row sm:items-center sm:justify-between">
        <Link href={`/cards?store_id=${store.id}`} className="w-full sm:w-auto">
          <Button variant="ghost" size="sm" className="w-full sm:w-auto">Product List</Button>
        </Link>
        <Link href={`/cards/new?store_id=${store.id}`} className="w-full sm:w-auto">
          <Button variant="outline" size="sm" className="w-full sm:w-auto">Create Card</Button>
        </Link>
      </div>
    </div>
  );
}
