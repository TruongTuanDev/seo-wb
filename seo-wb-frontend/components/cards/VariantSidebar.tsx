"use client";

import { Copy, ImagePlus, Loader2, Trash } from "lucide-react";
import { FilePreviewImage } from "@/components/cards/FilePreviewImage";
import type { ImageGenerationStatus } from "@/components/cards/MediaGallery";
import type { VariantCardState } from "@/components/cards/types";

interface VariantSidebarProps {
  variants: VariantCardState[];
  activeVariantId: string;
  fieldErrors: Record<string, string>;
  generationStatuses?: Record<string, ImageGenerationStatus>;
  onSelect: (variant: VariantCardState) => void;
  onDuplicate: (variant: VariantCardState) => void;
  onDelete: (variantId: string) => void;
}

export function VariantSidebar({
  variants,
  activeVariantId,
  fieldErrors,
  generationStatuses,
  onSelect,
  onDuplicate,
  onDelete,
}: VariantSidebarProps) {
  return (
    <aside className="space-y-4">
      <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-soft-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="font-semibold text-zinc-950">Color Variants</h2>
            <p className="text-xs text-zinc-500">{variants.length} card(s)</p>
          </div>
        </div>
        <div className="space-y-3">
          {variants.map((variant, index) => {
            const generationStatus = generationStatuses?.[variant.id];
            const isGenerating = generationStatus?.status === "queued" || generationStatus?.status === "processing";

            return (
              <div
                role="button"
                tabIndex={0}
                key={variant.id}
                onClick={() => onSelect(variant)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(variant);
                  }
                }}
                className={`w-full rounded-xl border p-3 text-left transition-all duration-200 hover:-translate-y-0.5 ${
                  fieldErrors[`${variant.id}.vendorCode`]
                    ? "border-rose-300 bg-rose-50"
                    : isGenerating
                      ? "border-indigo-300 bg-indigo-50/80"
                      : activeVariantId === variant.id
                        ? "border-brand bg-indigo-50"
                        : "border-zinc-200 bg-white hover:border-zinc-300 hover:shadow-soft-md"
                }`}
              >
                <div className="flex gap-3">
                  <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-lg border border-zinc-200 bg-zinc-50">
                    {variant.images[0] ? (
                      <FilePreviewImage file={variant.images[0]} className="h-full w-full object-cover" alt="" />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-zinc-400">
                        <ImagePlus size={20} />
                      </div>
                    )}
                    {isGenerating && (
                      <div className="absolute inset-0 flex items-center justify-center bg-white/70">
                        <Loader2 size={18} className="animate-spin text-brand" />
                      </div>
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="text-[11px] text-brand font-semibold">Variant {index + 1}</div>
                    <div className="truncate text-sm font-medium text-zinc-950">{variant.title || "Untitled card"}</div>
                    <div className="text-xs text-zinc-400 truncate">{variant.vendorCode || "No vendor code"}</div>
                    <div className="text-xs text-zinc-500 truncate">
                      {isGenerating
                        ? `Generating ${generationStatus?.progress || 0}/${generationStatus?.total || 0}`
                        : variant.color || "Color not set"}
                    </div>
                  </div>
                  <div className="ml-auto flex shrink-0 flex-col gap-1">
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        onDuplicate(variant);
                      }}
                      className="rounded-md p-1.5 text-zinc-500 transition-colors duration-150 hover:bg-zinc-100 hover:text-zinc-950"
                      title="Duplicate variant"
                    >
                      <Copy size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        onDelete(variant.id);
                      }}
                      disabled={variants.length <= 1}
                      className="rounded-md p-1.5 text-zinc-500 transition-colors duration-150 hover:bg-rose-50 hover:text-rose-500 disabled:opacity-30"
                      title="Delete variant"
                    >
                      <Trash size={14} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
