"use client";

import React from "react";
import type { RuntimeModelTemplate } from "@/lib/modelTemplates";
import { publicAssetUrl } from "@/lib/api";

interface ModelSelectorProps {
  selectedModelId: string;
  models: RuntimeModelTemplate[];
  onSelectModel: (model: RuntimeModelTemplate) => void;
}

export function ModelSelector({
  selectedModelId,
  models,
  onSelectModel,
}: ModelSelectorProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-zinc-800">
          Select Model <span className="text-brand">*</span>
        </label>
        <span className="text-[11px] text-zinc-500">
          {models.length} model{models.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="max-h-[420px] overflow-y-auto pr-1">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {models.map((model) => {
            const isSelected = selectedModelId === model.id;
            return (
              <button
                key={model.id}
                type="button"
                onClick={() => onSelectModel(model)}
                className="group relative flex flex-col items-center overflow-hidden rounded-xl border p-2.5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-soft-md border-zinc-200 bg-white"
                style={{
                  borderColor: isSelected ? "var(--brand, #4f46e5)" : "",
                  backgroundColor: isSelected ? "rgba(79, 70, 229, 0.05)" : "",
                  boxShadow: isSelected ? "0 0 0 2px rgba(79, 70, 229, 0.15)" : ""
                }}
              >
                <div className="relative aspect-[3/4] w-full overflow-hidden rounded-lg bg-zinc-50 border border-zinc-100">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={publicAssetUrl(model.frontImageUrl)}
                    alt={model.name}
                    className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                  />
                  
                  {isSelected && (
                    <div className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-brand text-white shadow-soft-sm animate-scale-in">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={3}
                        stroke="currentColor"
                        className="h-3 w-3"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="m4.5 12.75 6 6 9-13.5"
                        />
                      </svg>
                    </div>
                  )}
                </div>

                <div className="mt-2 w-full text-center">
                  <div className="text-xs font-semibold text-zinc-950">
                    {model.name}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

