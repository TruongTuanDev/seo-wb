"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useDropzone } from "react-dropzone";
import { ImagePlus, RotateCcw, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ImageDropzoneProps {
  files: File[];
  onChange: (files: File[]) => void;
  maxFiles?: number;
}

interface ImageSlotProps {
  label: string;
  hint: string;
  file?: File;
  previewUrl?: string;
  required?: boolean;
  disabled?: boolean;
  onSelect: (file: File) => void;
  onRemove: () => void;
  onZoom: () => void;
}

function ImageSlot({
  label,
  hint,
  file,
  previewUrl,
  required = false,
  disabled = false,
  onSelect,
  onRemove,
  onZoom,
}: ImageSlotProps) {
  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop: (acceptedFiles) => {
      const selected = acceptedFiles[0];
      if (selected) onSelect(selected);
    },
    accept: {
      "image/jpeg": [],
      "image/png": [],
      "image/webp": [],
    },
    maxFiles: 1,
    multiple: false,
    disabled,
    noClick: Boolean(file),
  });

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-zinc-900">
            {label}
            {required && <span className="ml-1 text-rose-500">*</span>}
          </div>
          <div className="text-xs text-zinc-500">{hint}</div>
        </div>
        {file && (
          <button
            type="button"
            onClick={open}
            className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700"
          >
            <RotateCcw size={13} />
            Thay ảnh
          </button>
        )}
      </div>

      <div
        {...getRootProps({
          onClick: file
            ? (event) => {
                event.preventDefault();
                onZoom();
              }
            : undefined,
        })}
        className={cn(
          "relative flex aspect-[3/4] min-h-52 overflow-hidden rounded-xl border-2 border-dashed transition-all duration-200",
          disabled
            ? "cursor-not-allowed border-zinc-200 bg-zinc-100 opacity-60"
            : isDragActive
              ? "border-indigo-500 bg-indigo-50 shadow-soft-md"
              : file
                ? "cursor-zoom-in border-zinc-200 bg-zinc-50 hover:border-indigo-300"
                : "cursor-pointer border-zinc-300 bg-zinc-50/70 hover:border-indigo-400 hover:bg-indigo-50/50"
        )}
      >
        <input {...getInputProps()} />
        {file && previewUrl ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={previewUrl} alt={label} className="h-full w-full object-contain" />
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onRemove();
              }}
              className="absolute right-2 top-2 rounded-full bg-rose-500 p-1.5 text-white shadow hover:bg-rose-600"
              aria-label={`Xóa ${label}`}
            >
              <X size={15} />
            </button>
          </>
        ) : (
          <div className="m-auto flex max-w-44 flex-col items-center px-4 text-center">
            <ImagePlus className={cn("mb-3 h-9 w-9", isDragActive ? "text-indigo-600" : "text-zinc-400")} />
            <div className="text-sm font-medium text-zinc-700">
              {isDragActive ? "Thả ảnh vào đây" : disabled ? "Nạp ảnh trước trước tiên" : "Chọn hoặc kéo ảnh vào"}
            </div>
            <div className="mt-1 text-xs text-zinc-500">JPG, PNG hoặc WEBP</div>
          </div>
        )}
      </div>
    </div>
  );
}

export function ImageDropzone({ files, onChange, maxFiles = 2 }: ImageDropzoneProps) {
  const [zoomUrl, setZoomUrl] = useState<string | null>(null);
  const [pendingBackImage, setPendingBackImage] = useState<File | null>(null);
  const limitedFiles = useMemo(
    () => files.slice(0, Math.min(maxFiles, 2)),
    [files, maxFiles]
  );
  const backImage = limitedFiles[1] || pendingBackImage || undefined;
  const previews = useMemo(
    () => [
      limitedFiles[0] ? URL.createObjectURL(limitedFiles[0]) : "",
      backImage ? URL.createObjectURL(backImage) : "",
    ],
    [limitedFiles, backImage]
  );

  useEffect(() => {
    return () => previews.forEach((url) => {
      if (url) URL.revokeObjectURL(url);
    });
  }, [previews]);

  const setFile = (index: number, file: File) => {
    if (index === 1 && !limitedFiles[0]) {
      setPendingBackImage(file);
      return;
    }
    if (index === 0 && pendingBackImage) {
      onChange([file, pendingBackImage]);
      setPendingBackImage(null);
      return;
    }
    const next = [...limitedFiles];
    next[index] = file;
    onChange(next.slice(0, 2));
  };

  const removeFile = (index: number) => {
    if (index === 0) {
      if (limitedFiles[1]) setPendingBackImage(limitedFiles[1]);
      onChange([]);
      return;
    }
    setPendingBackImage(null);
    onChange(limitedFiles.filter((_, fileIndex) => fileIndex !== index));
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <ImageSlot
          label="Ảnh mặt trước"
          hint="Ảnh chính để nhận diện sản phẩm"
          file={limitedFiles[0]}
          previewUrl={previews[0]}
          required
          onSelect={(file) => setFile(0, file)}
          onRemove={() => removeFile(0)}
          onZoom={() => setZoomUrl(previews[0] || null)}
        />
        <ImageSlot
          label="Ảnh mặt sau"
          hint="Khuyến nghị để nhận diện đầy đủ chi tiết"
          file={backImage}
          previewUrl={previews[1]}
          onSelect={(file) => setFile(1, file)}
          onRemove={() => removeFile(1)}
          onZoom={() => setZoomUrl(previews[1] || null)}
        />
      </div>

      <div className="rounded-lg bg-indigo-50 px-3 py-2 text-xs leading-relaxed text-indigo-800">
        AI sẽ dùng chung hai ảnh này để tạo thuộc tính, nội dung và ảnh sản phẩm. Bạn không cần tải lại ở bước sau.
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
              alt="Xem ảnh sản phẩm"
              onClick={(event) => event.stopPropagation()}
              className="max-h-full max-w-full cursor-default rounded-xl object-contain"
            />
          </div>,
          document.body
        )}
    </div>
  );
}
