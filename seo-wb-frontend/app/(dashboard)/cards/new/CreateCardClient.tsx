"use client";

import React, { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useRouter, useSearchParams } from "next/navigation";
import { Characteristic } from "@/components/cards/CharacteristicsEditor";
import { SizeRow } from "@/components/cards/SizeTable";
import { ImageGenerationStatus, MediaGallery, RecommendationPayload } from "@/components/cards/MediaGallery";
import { ProductDetailsForm } from "@/components/cards/ProductDetailsForm";
import { StepIndicator } from "@/components/cards/StepIndicator";
import { VariantSidebar } from "@/components/cards/VariantSidebar";
import type { VariantCardState } from "@/components/cards/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useStore } from "@/contexts/StoreContext";
import { useToast } from "@/contexts/ToastContext";
import { useCardForm } from "@/hooks/useCardForm";
import { useDraftAutosave } from "@/hooks/useDraftAutosave";
import { useJobStatus } from "@/hooks/useJobStatus";
import { API_BASE, api } from "@/lib/api";
import { ArrowRight, ArrowLeft, RefreshCw, CheckCircle, UploadCloud, ImagePlus, X } from "lucide-react";

type CreationMode = "create_new" | "add_to_existing_imt" | "create_then_merge";

interface WbCharacteristicSchema {
  charcID?: number;
  name?: string;
}

interface GeneratedCharacteristic {
  id?: number;
  name?: string;
  value?: Characteristic["value"];
}

interface GeneratedSize {
  techSize?: string;
  wbSize?: string;
  sku?: string;
  skus?: string[];
}

interface GeneratedVariant {
  title?: string;
  description?: string;
  vendorCode?: string;
  characteristics?: GeneratedCharacteristic[];
  sizes?: GeneratedSize[];
  brand?: string;
  media?: {
    cover?: string;
    local_files?: {
      url?: string;
      fileName?: string;
      photoNumber?: number;
    }[];
  };
  dimensions?: {
    length?: number;
    width?: number;
    height?: number;
    weightBrutto?: number;
  };
}

interface GeneratedGroup {
  subjectID?: number;
  variants?: GeneratedVariant[];
}

interface GenerateResponse {
  draft_id?: number;
  analysis?: {
    category?: string;
    material?: string;
    color?: string;
    gender?: string;
    attributes?: Record<string, string | undefined>;
    recommendations?: RecommendationPayload | null;
  };
  card_payload?: GeneratedGroup[];
}

interface DraftResponse {
  id: number;
  subject_id?: number;
  card_payload?: GeneratedGroup[];
  analysis?: {
    recommendations?: RecommendationPayload | null;
  } | null;
}

interface ImageGenerationJob {
  id: string;
  status: "queued" | "processing" | "completed" | "completed_with_warnings" | "failed" | "failed_validation" | string;
  step: string;
  progress: number;
  total: number;
  variant_id?: string;
  images: NonNullable<ImageGenerationStatus["images"]>;
  error?: string | null;
  job_type?: string;
  quality_report?: {
    catalog_score?: number;
  } | null;
  failed_validations?: ImageGenerationStatus["failed_validations"];
  seller_warning?: string | null;
  final_validation_status?: ImageGenerationStatus["final_validation_status"];
  validation_summary?: ImageGenerationStatus["validation_summary"];
}

function getErrorMessage(err: unknown) {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  try {
    return JSON.stringify(err);
  } catch {
    return "Unknown error";
  }
}

function DraftAutosaveBridge({
  draftId,
  payload,
  enabled,
}: {
  draftId: number | null;
  payload: unknown | null;
  enabled: boolean;
}) {
  useDraftAutosave({ draftId, payload, enabled });
  return null;
}

function mediaUrl(url?: string) {
  if (!url) return null;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return `${API_BASE}${url.startsWith("/") ? url : `/${url}`}`;
}

function imageFetchCredentials(url: string): RequestCredentials {
  return url.startsWith(API_BASE) ? "include" : "omit";
}

function fetchImage(url: string) {
  return fetch(url, { credentials: imageFetchCredentials(url) });
}

function fileNameFromUrl(url: string, fallback: string) {
  const name = url.split("/").pop()?.split("?")[0];
  return decodeURIComponent(name || fallback);
}

async function fileFromGeneratedUrl(url: string, fallbackName: string) {
  const fullUrl = mediaUrl(url);
  if (!fullUrl) return null;
  const response = await fetchImage(fullUrl);
  if (!response.ok) return null;
  const blob = await response.blob();
  return new File([blob], fallbackName, { type: blob.type || "image/png", lastModified: Date.now() });
}

async function loadDraftImages(variant: GeneratedVariant, variantIndex: number) {
  const localFiles = variant.media?.local_files || [];
  const mediaItems = localFiles.length
    ? localFiles
    : variant.media?.cover
      ? [{ url: variant.media.cover, fileName: `draft-${variantIndex + 1}-cover.jpg`, photoNumber: 1 }]
      : [];

  const sortedItems = [...mediaItems].sort((left, right) => (left.photoNumber || 0) - (right.photoNumber || 0));
  const files = await Promise.all(
    sortedItems.map(async (item, index) => {
      const url = mediaUrl(item.url);
      if (!url) return null;
      try {
        const response = await fetchImage(url);
        if (!response.ok) return null;
        const blob = await response.blob();
        const name = item.fileName || fileNameFromUrl(url, `draft-${variantIndex + 1}-${index + 1}.jpg`);
        return new File([blob], name, { type: blob.type || "image/jpeg", lastModified: Date.now() });
      } catch {
        return null;
      }
    })
  );
  return files.filter((file): file is File => Boolean(file));
}

function charcNameById(schema: WbCharacteristicSchema[], id?: number) {
  return schema.find((item) => Number(item.charcID) === Number(id))?.name;
}

function normalizeCharcName(value?: string) {
  return String(value || "").trim().toLowerCase();
}

function valueText(value?: Characteristic["value"]) {
  return Array.isArray(value) ? value.join("; ") : String(value || "");
}

function findCharacteristicValue(characteristics: Characteristic[], names: string[]) {
  const normalizedNames = names.map(normalizeCharcName);
  const item = characteristics.find((charc) => normalizedNames.includes(normalizeCharcName(charc.name)));
  return item ? valueText(item.value) : "";
}

function ReferenceImageInput({
  label,
  required,
  file,
  onChange,
  onRemove,
}: {
  label: string;
  required?: boolean;
  file: File | null;
  onChange: (file: File | null) => void;
  onRemove: () => void;
}) {
  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);

  useEffect(() => {
    if (!previewUrl) return;
    return () => URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  return (
    <label className="group relative flex min-h-48 cursor-pointer flex-col overflow-hidden rounded-xl border border-dashed border-zinc-300 bg-white transition-colors hover:border-brand hover:bg-indigo-50/30">
      {previewUrl ? (
        <div className="relative h-40 w-full bg-zinc-100">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={previewUrl} alt={label} className="h-full w-full object-contain p-2" />
          <button
            type="button"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onRemove();
            }}
            className="absolute right-2 top-2 rounded-full bg-rose-600 p-1.5 text-white opacity-0 transition-opacity group-hover:opacity-100"
          >
            <X size={14} />
          </button>
        </div>
      ) : (
        <div className="flex h-40 flex-col items-center justify-center p-4 text-center text-zinc-500">
          <ImagePlus size={28} className="mb-3" />
          <span className="text-sm font-medium">{label}</span>
          <span className="mt-1 text-xs">JPG, PNG, WEBP</span>
        </div>
      )}
      <div className="flex min-h-16 flex-col justify-center px-4 py-3">
        <span className="text-sm font-medium text-zinc-900">
          {label} {required && <span className="text-brand">*</span>}
        </span>
        <span className="mt-1 line-clamp-1 text-xs text-zinc-500">
          {file ? file.name : required ? "Required for analysis and generation" : "Optional back reference"}
        </span>
      </div>
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(event) => {
          onChange(event.target.files?.[0] || null);
          event.target.value = "";
        }}
      />
    </label>
  );
}

export function CreateCardClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { currentStoreId } = useStore();
  const storeId = currentStoreId ?? 0;
  const draftIdParam = searchParams.get("draft_id");
  const variantIndexParam = Number(searchParams.get("variant_index") || 0);
  const { success, error } = useToast();

  const {
    currentStep,
    setCurrentStep,
    isProcessing,
    setIsProcessing,
    formError,
    setFormError,
    fieldErrors,
    setFieldErrors,
  } = useCardForm();

  // Form State
  const [images, setImages] = useState<File[]>([]);
  const [subjectId, setSubjectId] = useState<number>(0);
  const [subjectName, setSubjectName] = useState<string>("");
  const [brand, setBrand] = useState("");
  const [vendorCode, setVendorCode] = useState("");
  const [, setColor] = useState("");
  const [gender, setGender] = useState("Женский");
  const [mode, setMode] = useState<"create_new" | "add_to_existing_imt" | "create_then_merge">("create_new");
  const [targetIMT, setTargetIMT] = useState("");
  const [note, setNote] = useState("");

  const [sizes, setSizes] = useState<SizeRow[]>([{ techSize: "", wbSize: "", sku: "" }]);
  const [dimensions, setDimensions] = useState({ length: 0, width: 0, height: 0, weightBrutto: 0 });

  // AI Generated / Edited state
  const [draftId, setDraftId] = useState<number | null>(null);
  const [, setGeneratedTitle] = useState("");
  const [, setGeneratedDesc] = useState("");
  const [, setCharcs] = useState<Characteristic[]>([]);
  const [, setAiAnalysis] = useState("");
  const [variants, setVariants] = useState<VariantCardState[]>([]);
  const [activeVariantId, setActiveVariantId] = useState<string>("");
  const [charcSchema, setCharcSchema] = useState<WbCharacteristicSchema[]>([]);
  const [draggedImageIndex, setDraggedImageIndex] = useState<number | null>(null);
  const [selectedPhotoIndex, setSelectedPhotoIndex] = useState(0);
  const [zoomImageUrl, setZoomImageUrl] = useState<string | null>(null);
  const [jobId, setJobId] = useState<number | null>(null);
  const { job } = useJobStatus(jobId);
  const [imageGenerationJobs, setImageGenerationJobs] = useState<Record<string, ImageGenerationJob>>({});
  const completedImageJobsRef = React.useRef<Set<string>>(new Set());
  const [recommendations, setRecommendations] = useState<RecommendationPayload | null>(null);

  useEffect(() => {
    return () => {
      if (zoomImageUrl?.startsWith("blob:")) {
        URL.revokeObjectURL(zoomImageUrl);
      }
    };
  }, [zoomImageUrl]);

  const openZoomImage = (file: File) => {
    setZoomImageUrl(URL.createObjectURL(file));
  };

  const closeZoomImage = () => {
    setZoomImageUrl(null);
  };

  useEffect(() => {
    if (!draftIdParam) return;

    const loadDraft = async () => {
      try {
        const draft = await api.get(`/cards/drafts/${draftIdParam}`) as DraftResponse;
        const group = draft.card_payload?.[0];
        const resolvedSubjectId = group?.subjectID || draft.subject_id || 0;
        let loadedCharcSchema: WbCharacteristicSchema[] = [];
        if (resolvedSubjectId) {
          const charcSchemaResponse = await api.get(`/wb/subjects/${resolvedSubjectId}/charcs?store_id=${storeId}`);
          loadedCharcSchema = charcSchemaResponse?.data || charcSchemaResponse || [];
          setCharcSchema(loadedCharcSchema);
        }
        const rawVariants = group?.variants || [];
        const loadedVariants = await Promise.all(rawVariants.map(async (variant: GeneratedVariant, index: number) => {
          const mappedCharcs = (variant.characteristics || []).map((item: GeneratedCharacteristic) => ({
            id: Number(item.id || 0),
            name: item.name || charcNameById(loadedCharcSchema, Number(item.id || 0)) || `Characteristic ${item.id}`,
            value: Array.isArray(item.value) ? item.value.join("; ") : String(item.value || ""),
          }));
          const variantColor = findCharacteristicValue(mappedCharcs, ["Цвет", "color"]);
          return {
            id: crypto.randomUUID(),
            title: variant.title || "",
            description: variant.description || "",
            vendorCode: variant.vendorCode || "",
            color: variantColor,
            images: await loadDraftImages(variant, index),
            characteristics: mappedCharcs,
            sizes: (variant.sizes || []).map((size: GeneratedSize) => ({
              techSize: String(size.techSize || "").trim(),
              wbSize: String(size.wbSize || "").trim(),
              sku: size.skus?.[0] || size.sku || "",
            })),
          };
        }));

        setDraftId(draft.id);
        setRecommendations(draft.analysis?.recommendations || null);
        setSubjectId(resolvedSubjectId);
        setVariants(loadedVariants);
        const selectedIndex = Number.isFinite(variantIndexParam) ? variantIndexParam : 0;
        const selectedVariant = loadedVariants[selectedIndex] || loadedVariants[0];
        const selectedPayloadVariant = rawVariants[selectedIndex] || rawVariants[0];
        if (selectedVariant) {
          setActiveVariantId(selectedVariant.id);
          setGeneratedTitle(selectedVariant.title);
          setGeneratedDesc(selectedVariant.description);
          setVendorCode(selectedVariant.vendorCode);
          setCharcs(selectedVariant.characteristics);
          setSizes(selectedVariant.sizes);
          setImages(selectedVariant.images);
          setColor(selectedVariant.color);
          const loadedGender = findCharacteristicValue(selectedVariant.characteristics, ["Пол", "gender"]);
          if (loadedGender) setGender(loadedGender);
        }
        if (selectedPayloadVariant?.brand) {
          setBrand(selectedPayloadVariant.brand);
        }
        if (selectedPayloadVariant?.dimensions) {
          setDimensions({
            length: selectedPayloadVariant.dimensions.length || 0,
            width: selectedPayloadVariant.dimensions.width || 0,
            height: selectedPayloadVariant.dimensions.height || 0,
            weightBrutto: selectedPayloadVariant.dimensions.weightBrutto || 0,
          });
        }
        setCurrentStep(2);
      } catch (err: unknown) {
        setFormError(getErrorMessage(err) || "Could not load saved card.");
      }
    };

    void loadDraft();
  }, [draftIdParam, setCurrentStep, setFormError, storeId, variantIndexParam]);

  const activeVariant = variants.find((variant) => variant.id === activeVariantId) || variants[0];
  const safeSelectedPhotoIndex = activeVariant?.images.length
    ? Math.min(selectedPhotoIndex, activeVariant.images.length - 1)
    : 0;

  const normalizeSizes = (rawSizes: GeneratedSize[]): SizeRow[] =>
    rawSizes.map((size) => {
      const techSize = String(size.techSize || "").trim();
      const wbSize = String(size.wbSize || "").trim();
      return {
        techSize,
        wbSize,
        sku: size.skus?.[0] || size.sku || "",
      };
    });

  const charcValueText = (value?: Characteristic["value"]) => Array.isArray(value) ? value.join("; ") : String(value || "");

  const upsertCharacteristicByName = (
    list: Characteristic[],
    schema: WbCharacteristicSchema[],
    names: string[],
    value?: string | null,
  ) => {
    const cleanValue = String(value || "").trim();
    if (!cleanValue) return list;
    const normalizedNames = names.map((name) => name.toLowerCase());
    const existing = list.find((item) => normalizedNames.includes(item.name.toLowerCase()));
    if (existing) {
      return list.map((item) => item.id === existing.id ? { ...item, value: cleanValue } : item);
    }
    const foundSchema = schema.find((item) => normalizedNames.includes(String(item.name || "").toLowerCase()));
    if (!foundSchema?.charcID) return list;
    return [...list, { id: Number(foundSchema.charcID), name: String(foundSchema.name), value: cleanValue }];
  };

  const updateActiveVariant = (patch: Partial<VariantCardState>) => {
    if (!activeVariant) return;
    setVariants((current) =>
      current.map((variant) => (variant.id === activeVariant.id ? { ...variant, ...patch } : variant))
    );
    if (patch.title !== undefined) setGeneratedTitle(patch.title);
    if (patch.description !== undefined) setGeneratedDesc(patch.description);
    if (patch.vendorCode !== undefined) setVendorCode(patch.vendorCode);
    if (patch.vendorCode !== undefined) {
      setFieldErrors((current) => {
        const next = { ...current };
        delete next[`${activeVariant.id}.vendorCode`];
        return next;
      });
    }
    if (patch.color !== undefined) setColor(patch.color);
    if (patch.characteristics !== undefined) setCharcs(patch.characteristics);
    if (patch.sizes !== undefined) setSizes(patch.sizes);
  };

  const selectVariant = (variant: VariantCardState) => {
    setActiveVariantId(variant.id);
    setSelectedPhotoIndex(0);
    setGeneratedTitle(variant.title);
    setGeneratedDesc(variant.description);
    setVendorCode(variant.vendorCode);
    setColor(variant.color);
    setCharcs(variant.characteristics);
    setSizes(variant.sizes);
  };

  const duplicateVariant = (variant: VariantCardState) => {
    const duplicate: VariantCardState = {
      ...variant,
      id: crypto.randomUUID(),
      vendorCode: variant.vendorCode ? `${variant.vendorCode}-COPY` : "",
      color: "",
      images: [],
      characteristics: variant.characteristics.filter((item) => {
        const normalizedName = item.name.toLowerCase();
        return normalizedName !== "цвет" && normalizedName !== "color";
      }),
    };
    setVariants((current) => [...current, duplicate]);
    selectVariant(duplicate);
  };

  const deleteVariant = (variantId: string) => {
    setVariants((current) => {
      if (current.length <= 1) return current;
      const next = current.filter((variant) => variant.id !== variantId);
      if (activeVariantId === variantId && next[0]) {
        setTimeout(() => selectVariant(next[0]), 0);
      }
      return next;
    });
  };

  const addImagesToActiveVariant = (files: FileList | File[]) => {
    if (!activeVariant) return;
    const incoming = Array.from(files).filter((file) => file.type.startsWith("image/"));
    const nextImages = [...activeVariant.images, ...incoming].slice(0, 10);
    updateActiveVariant({ images: nextImages });
    if (activeVariant.images.length === 0 && nextImages.length) setSelectedPhotoIndex(0);
  };

  const appendImagesToVariant = (variantId: string, files: File[]) => {
    if (!files.length) return;
    setVariants((current) =>
      current.map((variant) =>
        variant.id === variantId
          ? { ...variant, images: [...variant.images, ...files].slice(0, 30) }
          : variant
      )
    );
  };

  const removeActiveVariantImage = (index: number) => {
    if (!activeVariant) return;
    updateActiveVariant({ images: activeVariant.images.filter((_, imageIndex) => imageIndex !== index) });
  };

  const moveActiveVariantImage = (fromIndex: number, toIndex: number) => {
    if (!activeVariant || fromIndex === toIndex) return;
    const nextImages = [...activeVariant.images];
    const [moved] = nextImages.splice(fromIndex, 1);
    nextImages.splice(toIndex, 0, moved);
    updateActiveVariant({ images: nextImages });
    setSelectedPhotoIndex(toIndex);
  };

  const setActiveColor = (nextColor: string) => {
    const nextCharcs = upsertCharacteristicByName(activeVariant?.characteristics || [], charcSchema, ["Цвет", "color"], nextColor);
    updateActiveVariant({ color: nextColor, characteristics: nextCharcs });
  };

  const getCharacteristicValue = (names: string[]) => {
    const normalized = names.map((name) => name.toLowerCase());
    const item = activeVariant?.characteristics.find((charc) => normalized.includes(charc.name.toLowerCase()));
    if (!item) return "";
    return Array.isArray(item.value) ? item.value.join("; ") : String(item.value || "");
  };

  const setCharacteristicValue = (names: string[], value: string) => {
    if (!activeVariant) return;
    const normalized = names.map((name) => name.toLowerCase());
    const hasExisting = activeVariant.characteristics.some((charc) => normalized.includes(charc.name.toLowerCase()));
    const nextCharcs = hasExisting
      ? activeVariant.characteristics.map((charc) =>
          normalized.includes(charc.name.toLowerCase()) ? { ...charc, value } : charc
        )
      : upsertCharacteristicByName(activeVariant.characteristics, charcSchema, names, value);
    updateActiveVariant({ characteristics: nextCharcs });
  };

  const normalizeCharacteristicValue = (value: Characteristic["value"]) => {
    if (Array.isArray(value)) {
      return value.map((item) => String(item).trim()).filter(Boolean);
    }

    const text = String(value ?? "").trim();
    if (!text) return [];
    if (text.includes(";")) {
      return text.split(";").map((item) => item.trim()).filter(Boolean);
    }
    return [text];
  };

  const effectiveBrand = () => brand.trim() || "Нет бренда";
  const frontImage = images[0] || null;
  const backImage = images[1] || null;

  const setReferenceImage = (index: 0 | 1, file: File | null) => {
    setImages((current) => {
      const next = [...current];
      if (file) {
        next[index] = file;
      } else {
        next.splice(index, 1);
      }
      return next.filter(Boolean).slice(0, 2);
    });
  };

  const removeReferenceImage = (index: 0 | 1) => {
    setImages((current) => current.filter((_, imageIndex) => imageIndex !== index));
  };

  const buildVariantPayload = (variant: VariantCardState = activeVariant) => ({
    vendorCode: variant.vendorCode.trim(),
    title: variant.title.trim(),
    description: variant.description.trim(),
    brand: effectiveBrand(),
    dimensions,
    characteristics: variant.characteristics
      .filter((item) => item.id && String(item.value ?? "").trim())
      .map((item) => ({
        id: item.id,
        value: normalizeCharacteristicValue(item.value),
      })),
    sizes: variant.sizes
      .filter((item) => item.techSize || item.wbSize || item.sku)
      .map((item) => ({
        techSize: item.techSize || undefined,
        wbSize: item.wbSize || undefined,
        skus: item.sku ? [item.sku] : [],
      })),
  });

  const buildCardPayload = () => [
    {
      subjectID: subjectId,
      variants: variants.length ? variants.map((variant) => buildVariantPayload(variant)) : [buildVariantPayload()],
    },
  ];

  const buildJobFormData = () => {
    validateEditableVariants();
    const cardPayload = buildCardPayload();
    const formData = new FormData();
    const mediaItems: { vendorCode: string; photoNumber: number }[] = [];
    formData.append("store_id", storeId.toString());
    formData.append("mode", mode);
    formData.append("card_payload_json", JSON.stringify(cardPayload));
    if (draftId) formData.append("draft_id", draftId.toString());
    if ((mode === "add_to_existing_imt" || mode === "create_then_merge") && targetIMT.trim()) {
      formData.append("target_imt", targetIMT.trim());
    }

    for (const variant of variants) {
      variant.images.forEach((image, index) => {
        formData.append("files", image);
        mediaItems.push({ vendorCode: variant.vendorCode.trim(), photoNumber: index + 1 });
      });
    }
    formData.append("media_manifest_json", JSON.stringify({ items: mediaItems }));
    return formData;
  };

  const buildImageGenerationMetadata = (variant: VariantCardState) => ({
    title: variant.title,
    productName: variant.title,
    category: subjectName,
    subjectName,
    brand: effectiveBrand(),
    color: variant.color || findCharacteristicValue(variant.characteristics, ["Цвет", "color"]),
    material: findCharacteristicValue(variant.characteristics, ["Состав", "composition", "material"]),
    description: variant.description,
  });

  const focusVariantError = (variant: VariantCardState, field: string, message: string) => {
    selectVariant(variant);
    setFieldErrors({ [`${variant.id}.${field}`]: message });
    setFormError(message);
    setTimeout(() => {
      document.getElementById(`field-${field}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
  };

  const validateEditableVariants = () => {
    const editableVariants = variants.length ? variants : [];
    if (!editableVariants.length) {
      throw new Error("No generated variants found. Generate the card again.");
    }
    const invalidVariant = editableVariants.find(
      (variant) => !variant.title.trim() || !variant.description.trim() || !variant.vendorCode.trim()
    );
    if (invalidVariant) {
      const message = "Each variant must have title, description, and vendor code before push.";
      focusVariantError(invalidVariant, "vendorCode", message);
      throw new Error(message);
    }
    const seen = new Map<string, VariantCardState>();
    for (const variant of editableVariants) {
      const key = variant.vendorCode.trim().toLowerCase();
      const duplicate = seen.get(key);
      if (duplicate) {
        const message = `Vendor code "${variant.vendorCode}" is duplicated. Please edit this variant before push.`;
        focusVariantError(variant, "vendorCode", message);
        throw new Error(message);
      }
      seen.set(key, variant);
    }
    setFieldErrors({});
  };

  const handleGenerate = async () => {
    setFormError("");
    if (images.length === 0) {
      error("Images required", "Please upload 1-2 images");
      return;
    }
    if (images.length > 2) {
      error("Too many images", "AI analysis accepts at most 2 images. Extra photos can be added later in Edit Details.");
      return;
    }
    setIsProcessing(true);
    setCurrentStep(1); // Moving to Analyzing visually

    try {
      const formData = new FormData();
      formData.append("store_id", storeId.toString());
      
      const payload = {
        category: subjectName || undefined,
        subject_id: subjectId || undefined,
        brand: brand.trim() || undefined,
        vendor_code: vendorCode.trim() || undefined,
        gender,
        sizes: sizes.map(s => s.techSize || s.wbSize).filter(Boolean),
        dimensions: {},
        note,
        attributes: {}
      };
      
      formData.append("product_input_json", JSON.stringify(payload));
      images.forEach((img) => formData.append("images", img));

      const response = await api.post("/cards/generate", formData) as GenerateResponse;
      
      setDraftId(response.draft_id || 1);
      setRecommendations(response.analysis?.recommendations || null);
      setAiAnalysis(JSON.stringify(response.analysis || {}, null, 2));
      const generatedVariants = response.card_payload?.[0]?.variants || [];
      const generatedVariant = generatedVariants[0];
      const resolvedSubjectId = Number(response.card_payload?.[0]?.subjectID || subjectId || 0);
      if (!resolvedSubjectId) {
        throw new Error("AI could not resolve Wildberries subject. Select a subject manually and generate again.");
      }
      setSubjectId(resolvedSubjectId);
      setSubjectName(response.analysis?.category || subjectName || "");
      setGeneratedTitle(generatedVariant?.title || "");
      setGeneratedDesc(generatedVariant?.description || "");
      const charcSchemaResponse = await api.get(`/wb/subjects/${resolvedSubjectId}/charcs?store_id=${storeId}`);
      const charcSchema = charcSchemaResponse?.data || charcSchemaResponse || [];
      setCharcSchema(charcSchema);
      const mapGeneratedCharcs = (variant?: GeneratedVariant) => (variant?.characteristics || []).map((item: GeneratedCharacteristic) => ({
          id: Number(item.id || 0),
          name: item.name || charcSchema.find((schemaItem: WbCharacteristicSchema) => Number(schemaItem.charcID) === Number(item.id))?.name || `Characteristic ${item.id}`,
          value: charcValueText(item.value),
        }));
      const generatedCharcs = mapGeneratedCharcs(generatedVariant);
      const enrichedCharcs = [
        ["Состав", "composition", "material"],
        ["Цвет", "color"],
        ["Пол", "gender"],
      ].reduce((list, names) => {
        const value = names[0] === "Состав"
          ? (response.analysis?.material || response.analysis?.attributes?.["Состав"])
          : names[0] === "Цвет"
            ? (response.analysis?.color || response.analysis?.attributes?.["Цвет"])
            : (response.analysis?.gender || response.analysis?.attributes?.["Пол"] || gender);
        return upsertCharacteristicByName(list, charcSchema, names, value);
      }, generatedCharcs as Characteristic[]);
      const generatedColor = charcValueText(
        enrichedCharcs.find((item) => item.name.toLowerCase() === "цвет" || item.name.toLowerCase() === "color")?.value || response.analysis?.color || ""
      );
      setCharcs(enrichedCharcs);
      let generatedSizes = sizes;
      if (generatedVariant?.sizes) {
        generatedSizes = normalizeSizes(generatedVariant.sizes);
        setSizes(generatedSizes);
      }
      if (generatedVariant?.dimensions) {
        setDimensions({
          length: generatedVariant.dimensions.length || 0,
          width: generatedVariant.dimensions.width || 0,
          height: generatedVariant.dimensions.height || 0,
          weightBrutto: generatedVariant.dimensions.weightBrutto || 0,
        });
      }

      const nextVariants: VariantCardState[] = (generatedVariants.length ? generatedVariants : [generatedVariant]).map((variant: GeneratedVariant | undefined, index: number) => {
        const variantCharcs = index === 0 ? enrichedCharcs : mapGeneratedCharcs(variant);
        const variantColor = charcValueText(
          variantCharcs.find((item: Characteristic) => item.name.toLowerCase() === "цвет" || item.name.toLowerCase() === "color")?.value || ""
        );
        return {
          id: crypto.randomUUID(),
          title: variant?.title || "",
          description: variant?.description || "",
          vendorCode: variant?.vendorCode === "CHANGE-ME" ? "" : (variant?.vendorCode || ""),
          color: variantColor || generatedColor,
          images: index === 0 ? images : [],
          characteristics: variantCharcs,
          sizes: variant?.sizes ? normalizeSizes(variant.sizes) : generatedSizes,
        };
      });
      const firstVariant = nextVariants[0];
      if (!firstVariant) {
        throw new Error("AI did not return any product variants.");
      }
      setVariants(nextVariants);
      setActiveVariantId(firstVariant.id);
      setJobId(null);

      setCurrentStep(2); // Move to Edit
      success("Generation Complete");
    } catch (err: unknown) {
      error("Generation failed", getErrorMessage(err));
      setCurrentStep(0); // Back to inputs
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCreateAndPublish = async () => {
    setIsProcessing(true);
    setFormError("");
    try {
      const job = await api.post("/cards/jobs", buildJobFormData());
      setJobId(Number(job.id));
      setCurrentStep(3);
      success("Card job queued", `Job #${job.id} is running in the background.`);
    } catch (err: unknown) {
      setFormError(getErrorMessage(err));
      setCurrentStep(2);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleGenerateVariantImages = async (
    variant: VariantCardState,
    input: {
      frontImage?: File;
      backImage?: File;
      modelImage?: File;
      modelId?: string;
      selectedModelImageUrl?: string;
      selectedModelGender?: string;
      selectedModelBodyType?: string;
      posePack?: string;
      backgroundStyle?: string;
      quantity: number;
      jobType: "openai" | "try_on" | "gpt_image" | "gpt_image_openai";
      productCategory?: string;
      garmentType?: string;
      imageModel?: string;
      autoGenerateModel?: boolean;
    }
  ) => {
    if (!draftId) {
      error("Draft required", "Generate AI card content before creating product images.");
      return;
    }
    const variantIndex = variants.findIndex((item) => item.id === variant.id);
    if (variantIndex < 0) return;
    const formData = new FormData();
    formData.append("store_id", String(storeId));
    formData.append("variant_id", variant.id);
    formData.append("variant_index", String(variantIndex));
    formData.append("quantity", String(input.quantity));

    let endpoint = "";
    if (input.jobType === "gpt_image" || input.jobType === "gpt_image_openai") {
      endpoint = input.jobType === "gpt_image_openai"
        ? `/cards/drafts/${draftId}/gpt-image-openai/jobs`
        : `/cards/drafts/${draftId}/gpt-image/jobs`;
      formData.append("selectedModelId", input.modelId || "");
      formData.append("selectedModelImageUrl", input.selectedModelImageUrl || "");
      formData.append("selectedModelGender", input.selectedModelGender || "");
      formData.append("selectedModelBodyType", input.selectedModelBodyType || "");
      formData.append("style", input.backgroundStyle || "studio");
      formData.append("autoGenerateModel", input.autoGenerateModel ? "true" : "false");
      if (input.frontImage) {
        formData.append("productFrontImage", input.frontImage);
      }
      if (input.backImage) {
        formData.append("productBackImage", input.backImage);
      }
      if (input.imageModel) {
        formData.append("model", input.imageModel);
      }
      if (input.modelImage) {
        formData.append("modelImage", input.modelImage);
      }
    } else if (input.jobType === "try_on") {
      endpoint = `/cards/drafts/${draftId}/try-on/jobs`;
      formData.append("selectedModelId", input.modelId || "");
      formData.append("selectedModelImageUrl", input.selectedModelImageUrl || "");
      formData.append("selectedModelGender", input.selectedModelGender || "");
      formData.append("selectedModelBodyType", input.selectedModelBodyType || "");
      formData.append("posePack", input.posePack || "");
      formData.append("backgroundStyle", input.backgroundStyle || "none");
      if (input.frontImage) {
        formData.append("productFrontImage", input.frontImage);
      }
      if (input.backImage) {
        formData.append("productBackImage", input.backImage);
      }
      if (input.productCategory) {
        formData.append("productCategory", input.productCategory);
      }
      if (input.garmentType) {
        formData.append("garmentType", input.garmentType);
      }
    } else {
      endpoint = `/cards/drafts/${draftId}/image-generation/jobs`;
      formData.append("metadata_json", JSON.stringify(buildImageGenerationMetadata(variant)));
      if (input.frontImage) {
        formData.append("front_image", input.frontImage);
      }
      if (input.backImage) {
        formData.append("back_image", input.backImage);
      }
      if (input.modelImage) formData.append("model_image", input.modelImage);
    }

    try {
      const imageJob = await api.post(endpoint, formData) as ImageGenerationJob;
      setImageGenerationJobs((current) => ({ ...current, [variant.id]: imageJob }));
      success("Image generation queued");
    } catch (err: unknown) {
      error("Image generation failed", getErrorMessage(err));
    }
  };

  useEffect(() => {
    if (!draftId) return;
    const activeJobs = Object.values(imageGenerationJobs).filter((imageJob) =>
      ["queued", "processing"].includes(imageJob.status)
    );
    if (!activeJobs.length) return;

    let cancelled = false;
    const timeoutId = window.setTimeout(async () => {
      const updates: Record<string, ImageGenerationJob> = {};
      await Promise.all(
        activeJobs.map(async (imageJob) => {
          try {
            let pollEndpoint = `/cards/drafts/${draftId}/image-generation/jobs/${imageJob.id}`;
            if (imageJob.job_type === "gpt_image") {
              pollEndpoint = `/cards/drafts/${draftId}/gpt-image/jobs/${imageJob.id}`;
            } else if (imageJob.job_type === "gpt_image_openai") {
              pollEndpoint = `/cards/drafts/${draftId}/gpt-image-openai/jobs/${imageJob.id}`;
            } else if (imageJob.job_type === "try_on") {
              pollEndpoint = `/cards/drafts/${draftId}/try-on/jobs/${imageJob.id}`;
            }
            const nextJob = await api.get(pollEndpoint) as ImageGenerationJob;
            updates[nextJob.variant_id || imageJob.variant_id || ""] = nextJob;
          } catch (err: unknown) {
            console.warn("Failed to poll image generation job", err);
          }
        })
      );
      if (cancelled || !Object.keys(updates).length) return;
      setImageGenerationJobs((current) => {
        const next = { ...current };
        Object.entries(updates).forEach(([variantId, imageJob]) => {
          if (variantId) next[variantId] = imageJob;
        });
        return next;
      });
    }, 2200);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [draftId, imageGenerationJobs]);

  useEffect(() => {
    const completedJobs = Object.values(imageGenerationJobs).filter(
      (imageJob) => ["completed", "completed_with_warnings"].includes(imageJob.status) && !completedImageJobsRef.current.has(imageJob.id)
    );
    if (!completedJobs.length) return;

    completedJobs.forEach((imageJob) => {
      completedImageJobsRef.current.add(imageJob.id);
      queueMicrotask(async () => {
        const files = (
          await Promise.all(
            (imageJob.images || []).map((item, index) =>
              fileFromGeneratedUrl(item.url, item.fileName || `generated-${index + 1}.jpg`)
            )
          )
        ).filter((file): file is File => Boolean(file));
        if (files.length && imageJob.variant_id) {
          appendImagesToVariant(imageJob.variant_id, files);
          success("Generated images added", `${files.length} image(s) added to the product card.`);
        }
      });
    });
  }, [imageGenerationJobs, success]);

  useEffect(() => {
    Object.values(imageGenerationJobs).forEach((imageJob) => {
      if (imageJob.status === "failed" && !completedImageJobsRef.current.has(imageJob.id)) {
        completedImageJobsRef.current.add(imageJob.id);
        error("Image generation failed", imageJob.error || "The worker could not generate images for this card.");
      }
      if (imageJob.status === "failed_validation" && !completedImageJobsRef.current.has(imageJob.id)) {
        completedImageJobsRef.current.add(imageJob.id);
      }
    });
  }, [imageGenerationJobs, error]);

  if (!storeId) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center shadow-soft-sm">
        <h2 className="mb-4 text-xl font-semibold text-zinc-950">No Store Selected</h2>
        <Button onClick={() => router.push("/")} variant="brand">Go to Dashboard</Button>
      </div>
    );
  }

  const handleSaveDraft = async () => {
    setIsProcessing(true);
    setFormError("");
    try {
      if (!draftId) {
        throw new Error("Draft ID is missing. Generate the card before saving.");
      }
      validateEditableVariants();
      const editedPayload = buildCardPayload();
      await api.put(`/cards/drafts/${draftId}`, { card_payload: editedPayload });
      success("Card draft updated");
    } catch (err: unknown) {
      setFormError(getErrorMessage(err));
      setCurrentStep(2);
    } finally {
      setIsProcessing(false);
    }
  };

  const safeBuildAutosavePayload = () => {
    try {
      if (!draftId || !subjectId || !variants.length) return null;
      if (!variants.every((variant) => variant.title.trim() && variant.description.trim() && variant.vendorCode.trim())) return null;
      if (!dimensions.length || !dimensions.width || !dimensions.height || !dimensions.weightBrutto) return null;
      return buildCardPayload();
    } catch {
      return null;
    }
  };

  // ====== RENDERERS FOR STEPS ======
  
  const renderInputs = () => (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <aside className="min-w-0 space-y-4">
          <div className="space-y-5 rounded-xl border border-zinc-200 bg-white p-6 shadow-soft-sm xl:sticky xl:top-24">
            <div>
              <h2 className="flex items-center gap-2 text-lg font-semibold text-zinc-950">
                <UploadCloud className="text-brand" size={20} /> Product Images
              </h2>
            </div>
            <div className="grid gap-4">
              <ReferenceImageInput
                label="Front Product Image"
                required
                file={frontImage}
                onChange={(file) => setReferenceImage(0, file)}
                onRemove={() => removeReferenceImage(0)}
              />
              <ReferenceImageInput
                label="Back Product Image"
                file={backImage}
                onChange={(file) => setReferenceImage(1, file)}
                onRemove={() => removeReferenceImage(1)}
              />
            </div>
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-600">
              Front image is used as the main garment reference. Back image is optional and enables back-view generations.
            </div>
          </div>
        </aside>

        <section className="space-y-5">
          <div className="space-y-5 rounded-xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
            <h2 className="text-lg font-semibold text-zinc-950">Generation Strategy</h2>

            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-700">Creation Mode</label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as CreationMode)}
                  className="flex h-10 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-soft-sm transition-colors duration-150 focus:border-brand focus:outline-none focus:ring-2 focus:ring-indigo-100"
                >
                  <option value="create_new">Create New Independent Card</option>
                  <option value="add_to_existing_imt">Add Variant to Existing Card (/upload/add)</option>
                  <option value="create_then_merge">Create New & Then Merge (Safe)</option>
                </select>
              </div>

              {(mode === "add_to_existing_imt" || mode === "create_then_merge") && (
                <Input label="Target IMT ID *" value={targetIMT} onChange={e=>setTargetIMT(e.target.value)} placeholder="e.g. 1630843654" />
              )}

              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-700">User Setup Prompts / Notes (Optional)</label>
                <textarea
                  value={note}
                  onChange={e => setNote(e.target.value)}
                  placeholder="e.g. женские брюки, черный цвет, хлопок, высокая посадка"
                  className="h-28 w-full rounded-md border border-zinc-300 bg-white p-3 text-sm text-zinc-900 shadow-soft-sm transition-colors duration-150 placeholder:text-zinc-400 focus:border-brand focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
              </div>
            </div>
          </div>

          <div className="space-y-5 rounded-xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
            <h2 className="text-lg font-semibold text-zinc-950">Basic Config</h2>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Input label="Brand" value={brand} onChange={e=>setBrand(e.target.value)} placeholder="Нет бренда" />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <Button variant="brand" size="lg" onClick={handleGenerate} disabled={isProcessing}>
              Generate AI Content <ArrowRight size={18} className="ml-2" />
            </Button>
          </div>
        </section>
      </div>
    </div>
  );

  const renderAnalyzing = () => (
    <div className="flex flex-col items-center justify-center space-y-6 rounded-xl border border-zinc-200 bg-white p-20 shadow-soft-sm">
       <RefreshCw size={48} className="text-brand animate-spin" />
       <h2 className="text-2xl font-semibold text-zinc-950">Analyzing & Generating...</h2>
    </div>
  );

  const renderEdit = () => (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
       <div className="grid grid-cols-1 gap-6 xl:grid-cols-[260px_minmax(0,1fr)_320px]">
          <VariantSidebar
            variants={variants}
            activeVariantId={activeVariant?.id || ""}
            fieldErrors={fieldErrors}
            generationStatuses={imageGenerationJobs as Record<string, ImageGenerationStatus>}
            onSelect={selectVariant}
            onDuplicate={duplicateVariant}
            onDelete={deleteVariant}
          />

         <ProductDetailsForm
           storeId={storeId}
           subjectId={subjectId}
           subjectName={subjectName}
           brand={brand}
           gender={gender}
           dimensions={dimensions}
           activeVariant={activeVariant}
           fieldErrors={fieldErrors}
           effectiveBrand={effectiveBrand}
           onSetSubject={async (id, name) => {
             setSubjectId(id);
             setSubjectName(name);
             try {
               const charcSchemaResponse = await api.get(`/wb/subjects/${id}/charcs?store_id=${storeId}`);
               setCharcSchema(charcSchemaResponse?.data || charcSchemaResponse || []);
             } catch (err: unknown) {
               error("Failed to fetch subject characteristics", getErrorMessage(err));
             }
           }}
           onSetBrand={setBrand}
           onSetGender={setGender}
           onSetDimensions={setDimensions}
           onUpdateVariant={updateActiveVariant}
           onSetActiveColor={setActiveColor}
           getCharacteristicValue={getCharacteristicValue}
           setCharacteristicValue={setCharacteristicValue}
         />

         <MediaGallery
           variant={activeVariant}
           selectedPhotoIndex={safeSelectedPhotoIndex}
           draggedImageIndex={draggedImageIndex}
           generationStatus={activeVariant ? imageGenerationJobs[activeVariant.id] as ImageGenerationStatus | undefined : undefined}
           onSelectPhoto={setSelectedPhotoIndex}
           onSetDraggedImageIndex={setDraggedImageIndex}
           onAddImages={addImagesToActiveVariant}
           onGenerateImages={(input) => {
             if (activeVariant) void handleGenerateVariantImages(activeVariant, input);
           }}
           onMoveImage={moveActiveVariantImage}
           onRemoveImage={removeActiveVariantImage}
           onZoomImage={openZoomImage}
           onJobUpdate={(jobUpdate) => {
             if (!activeVariant) return;
             setImageGenerationJobs((current) => ({ ...current, [activeVariant.id]: jobUpdate as ImageGenerationJob }));
           }}
           productCategory={subjectName}
           recommendations={recommendations}
           draftId={draftId || undefined}
         />
       </div>

       <div className="mt-8 flex flex-col gap-4 border-t border-zinc-200 pt-6 sm:flex-row sm:justify-between">
          <Button
            variant="outline"
            onClick={() => draftId ? router.push("/cards") : setCurrentStep(0)}
            className="w-full sm:w-auto"
          >
            <ArrowLeft size={16} className="mr-2" /> {draftId ? "Back to Product Cards" : "Back to Inputs"}
          </Button>
          <div className="flex w-full max-w-xl flex-col gap-3 sm:items-end">
            {formError && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-right text-sm text-rose-700">
                {formError}
              </div>
            )}
            <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:flex-wrap sm:justify-end">
              {draftId && (
                <Button variant="outline" onClick={handleSaveDraft} isLoading={isProcessing} className="w-full sm:w-auto">
                  Save Draft
                </Button>
              )}
              <Button variant="brand" onClick={handleCreateAndPublish} isLoading={isProcessing} className="w-full sm:w-auto">
                Verify, Push & Upload Media <ArrowRight size={16} className="ml-2" />
              </Button>
            </div>
          </div>
       </div>
    </div>
  );

  const renderDone = () => (
    <div className="space-y-6 animate-in zoom-in-95 duration-500">
       {job?.status === "completed" ? (
         <div className="flex flex-col items-center justify-center rounded-xl border border-emerald-200 bg-emerald-50 p-12 text-center shadow-soft-sm">
           <div className="text-brand">
              <CheckCircle size={64} />
           </div>
           <h1 className="mt-4 text-3xl font-semibold text-zinc-950">All Set!</h1>
           <p className="mt-2 text-sm text-zinc-600">Card creation, WB push, and media upload finished.</p>
           <div className="pt-8">
              <Button variant="outline" size="lg" onClick={() => router.push("/cards")}>Return to Product Cards</Button>
           </div>
         </div>
       ) : (
         <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center shadow-soft-sm">
           <h1 className="text-2xl font-semibold text-zinc-950">
             {job?.status === "failed" ? "Job needs user fix" : "Card job is running"}
           </h1>
           <p className="mt-2 text-sm text-zinc-500">
             {job?.status === "failed"
               ? "Fix the highlighted fields, then push again."
               : "You can stay on this page while the backend validates, pushes, and uploads media."}
           </p>
           <div className="mt-6 flex justify-center gap-3">
             <Button variant="outline" onClick={() => setCurrentStep(2)}>Edit Details</Button>
            <Button variant="brand" onClick={() => router.push("/cards")}>Product Cards</Button>
           </div>
         </div>
       )}
    </div>
  );

  return (
    <div className="mx-auto w-full max-w-[1400px] pb-20">
      <DraftAutosaveBridge
        draftId={draftId}
        enabled={currentStep === 2 && !isProcessing}
        payload={safeBuildAutosavePayload()}
      />
      <div className="mb-8">
        <StepIndicator currentStep={currentStep} job={jobId ? job : null} />
      </div>
      <div>
        {currentStep === 0 && renderInputs()}
        {currentStep === 1 && renderAnalyzing()}
        {currentStep === 2 && renderEdit()}
        {currentStep === 3 && renderDone()}
      </div>
      {zoomImageUrl && typeof document !== "undefined" &&
        createPortal(
          <div
            role="presentation"
            onClick={closeZoomImage}
            className="fixed inset-0 z-[9999] flex cursor-zoom-out items-center justify-center bg-black/85 p-6"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={zoomImageUrl}
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
