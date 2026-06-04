"use client";

import React from "react";
import { Input } from "@/components/ui/Input";
import type { GroupBy } from "@/lib/types/finance";
import { cn } from "@/lib/utils";

interface FinanceDateRangeFilterProps {
  dateFrom: string;
  dateTo: string;
  groupBy: GroupBy;
  onDateFromChange: (v: string) => void;
  onDateToChange: (v: string) => void;
  onGroupByChange: (v: GroupBy) => void;
  className?: string;
}

const GROUP_BY_OPTIONS: { value: GroupBy; label: string }[] = [
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "year", label: "Year" },
];

export function FinanceDateRangeFilter({
  dateFrom,
  dateTo,
  groupBy,
  onDateFromChange,
  onDateToChange,
  onGroupByChange,
  className,
}: FinanceDateRangeFilterProps) {
  return (
    <div className={cn("flex flex-wrap items-end gap-3", className)}>
      <div className="w-36">
        <Input
          label="Date from"
          type="date"
          value={dateFrom}
          onChange={(e) => onDateFromChange(e.target.value)}
          max={dateTo}
        />
      </div>

      <div className="w-36">
        <Input
          label="Date to"
          type="date"
          value={dateTo}
          onChange={(e) => onDateToChange(e.target.value)}
          min={dateFrom}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-zinc-700">Group by</span>
        <div className="flex rounded-md border border-zinc-300 bg-white shadow-soft-sm overflow-hidden">
          {GROUP_BY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => onGroupByChange(opt.value)}
              className={cn(
                "px-3 py-2 text-sm font-medium transition-colors duration-150",
                groupBy === opt.value
                  ? "bg-brand text-white"
                  : "text-zinc-600 hover:bg-zinc-50"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
