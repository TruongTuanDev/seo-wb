"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useDropzone } from "react-dropzone";
import { ImagePlus, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ImageDropzoneProps {
  files: File[];
  onChange: (files: File[]) => void;
  maxFiles?: number;
}

export function ImageDropzone({ files, onChange, maxFiles = 10 }: ImageDropzoneProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [zoomUrl, setZoomUrl] = useState<string | null>(null);

  const previews = useMemo(
    () => files.map((file) => ({
      id: `${file.name}-${file.size}-${file.lastModified}`,
      url: URL.createObjectURL(file),
    })),
    [files]
  );

  useEffect(() => {
    return () => {
      previews.forEach((preview) => URL.revokeObjectURL(preview.url));
    };
  }, [previews]);

  const safeSelectedIndex = previews.length ? Math.min(selectedIndex, previews.length - 1) : 0;

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const newFiles = [...files, ...acceptedFiles].slice(0, maxFiles);
      onChange(newFiles);
      setSelectedIndex(files.length ? files.length : 0);
    },
    [files, maxFiles, onChange]
  );

  const removeFile = (index: number) => {
    onChange(files.filter((_, i) => i !== index));
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "image/jpeg": [],
      "image/png": [],
      "image/webp": [],
    },
    maxFiles: maxFiles - files.length,
    disabled: files.length >= maxFiles,
  });

  return (
    <div className="w-full space-y-4">
      {previews.length > 0 && (
        <div className="space-y-3">
          <button
            type="button"
            onClick={() => setZoomUrl(previews[safeSelectedIndex]?.url || null)}
            className="group relative block w-full overflow-hidden rounded-xl border border-zinc-200 bg-zinc-50 transition-all duration-200 hover:border-zinc-300 hover:shadow-soft-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={previews[safeSelectedIndex]?.url}
              alt={`Preview ${safeSelectedIndex + 1}`}
              draggable={false}
              className="max-h-[360px] w-full object-contain transition-transform duration-300 group-hover:scale-[1.01] sm:max-h-[460px]"
            />
            <span className="absolute left-3 top-3 rounded-full bg-black/70 px-2.5 py-1 text-xs text-white">
              {safeSelectedIndex + 1} / {previews.length}
            </span>
          </button>

          <div className="grid grid-cols-2 gap-3">
            {previews.map((preview, index) => (
              <button
                type="button"
                key={preview.id}
                onClick={() => setSelectedIndex(index)}
                className={cn(
                  "group relative aspect-[4/3] overflow-hidden rounded-lg border bg-white transition-all duration-200 hover:-translate-y-0.5 hover:shadow-soft-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2",
                  selectedIndex === index ? "border-brand" : "border-zinc-200"
                )}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={preview.url}
                  alt={`Preview ${index + 1}`}
                  draggable={false}
                  className="h-full w-full object-cover"
                />
                <div className="absolute left-1 top-1 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white backdrop-blur-sm">
                  {index + 1}
                </div>
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(event) => {
                    event.stopPropagation();
                    removeFile(index);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      event.stopPropagation();
                      removeFile(index);
                    }
                  }}
                  className="absolute right-2 top-2 rounded-full bg-rose-500/90 p-1.5 text-white opacity-0 backdrop-blur-sm transition-opacity duration-150 group-hover:opacity-100 hover:bg-rose-600"
                >
                  <X className="h-4 w-4" />
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div
        {...getRootProps()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition-all duration-200",
          isDragActive
            ? "border-indigo-400 bg-indigo-50/50 text-brand shadow-soft-md"
            : files.length >= maxFiles
              ? "cursor-not-allowed border-zinc-200 bg-zinc-100 text-zinc-400 opacity-60"
              : "border-zinc-300 text-zinc-500 hover:border-indigo-400 hover:bg-indigo-50/50"
        )}
      >
        <input {...getInputProps()} />
        <ImagePlus className={cn("mb-2 h-9 w-9", isDragActive ? "text-brand" : "text-zinc-500")} />
        {files.length >= maxFiles ? (
          <p className="text-sm font-medium">Maximum {maxFiles} images reached</p>
        ) : isDragActive ? (
          <p className="text-sm font-medium">Drop images here</p>
        ) : (
          <p className="text-sm font-medium">Drag & drop images here, or click to select files</p>
        )}
      </div>

      {zoomUrl && typeof document !== "undefined" &&
        createPortal(
          <div
            role="presentation"
            onClick={() => setZoomUrl(null)}
            className="fixed inset-0 z-[9999] flex cursor-zoom-out items-center justify-center bg-black/85 p-6"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={zoomUrl}
              alt="Large preview"
              onClick={(event) => event.stopPropagation()}
              className="max-h-full max-w-full cursor-default rounded-xl object-contain"
            />
          </div>,
          document.body
        )}
    </div>
  );
}
