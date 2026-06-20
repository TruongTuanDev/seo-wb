"use client";

import { startTransition, useEffect, useState } from "react";
import { GripVertical, ImagePlus, Loader2, WandSparkles, X } from "lucide-react";
import { FilePreviewImage } from "@/components/cards/FilePreviewImage";
import type { VariantCardState } from "@/components/cards/types";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { ModelSelector } from "@/components/cards/ModelSelector";
import { API_BASE, api, publicAssetUrl } from "@/lib/api";
import { fetchRuntimeAiStudioSettings, fetchRuntimeModelTemplates, RuntimeModelTemplate } from "@/lib/modelTemplates";
import { fetchShopModels, type ShopModel } from "@/lib/shopModels";
import { useStore } from "@/contexts/StoreContext";

export const CATEGORY_TO_GARMENT_TYPE: Record<string, string> = {
  "shirt": "upper_body",
  "t-shirt": "upper_body",
  "hoodie": "upper_body",
  "jacket": "upper_body",
  "pants": "lower_body",
  "jeans": "lower_body",
  "shorts": "lower_body",
  "skirt": "lower_body",
  "dress": "full_body",
  "set": "full_body"
};

export function getGarmentType(category: string): string {
  const cat = (category || "").toLowerCase().trim();
  if (cat.includes("брюки") || cat.includes("штаны") || cat.includes("леггинсы") || cat.includes("джоггеры") || cat.includes("pants")) {
    return CATEGORY_TO_GARMENT_TYPE["pants"];
  }
  if (cat.includes("джинсы") || cat.includes("jeans")) {
    return CATEGORY_TO_GARMENT_TYPE["jeans"];
  }
  if (cat.includes("шорты") || cat.includes("shorts")) {
    return CATEGORY_TO_GARMENT_TYPE["shorts"];
  }
  if (cat.includes("юбк") || cat.includes("skirt")) {
    return CATEGORY_TO_GARMENT_TYPE["skirt"];
  }
  if (cat.includes("плать") || cat.includes("сарафан") || cat.includes("dress")) {
    return CATEGORY_TO_GARMENT_TYPE["dress"];
  }
  if (cat.includes("костюм") || cat.includes("комбинезон") || cat.includes("комплект") || cat.includes("set")) {
    return CATEGORY_TO_GARMENT_TYPE["set"];
  }
  if (cat.includes("рубаш") || cat.includes("блуз") || cat.includes("shirt")) {
    return CATEGORY_TO_GARMENT_TYPE["shirt"];
  }
  if (cat.includes("футболк") || cat.includes("майк") || cat.includes("топ") || cat.includes("t-shirt")) {
    return CATEGORY_TO_GARMENT_TYPE["t-shirt"];
  }
  if (cat.includes("худи") || cat.includes("свитшот") || cat.includes("толстовк") || cat.includes("джемпер") || cat.includes("свитер") || cat.includes("пуловер") || cat.includes("кардиган") || cat.includes("hoodie")) {
    return CATEGORY_TO_GARMENT_TYPE["hoodie"];
  }
  if (cat.includes("куртк") || cat.includes("пальто") || cat.includes("пиджак") || cat.includes("жилет") || cat.includes("ветровк") || cat.includes("бомбер") || cat.includes("jacket")) {
    return CATEGORY_TO_GARMENT_TYPE["jacket"];
  }
  return "upper_body";
}

export function getEnglishCategoryKey(category: string): string {
  const cat = (category || "").toLowerCase().trim();
  if (cat.includes("брюки") || cat.includes("штаны") || cat.includes("леггинсы") || cat.includes("джоггеры") || cat.includes("pants")) {
    return "pants";
  }
  if (cat.includes("джинсы") || cat.includes("jeans")) {
    return "jeans";
  }
  if (cat.includes("шорты") || cat.includes("shorts")) {
    return "shorts";
  }
  if (cat.includes("юбк") || cat.includes("skirt")) {
    return "skirt";
  }
  if (cat.includes("плать") || cat.includes("сарафан") || cat.includes("dress")) {
    return "dress";
  }
  if (cat.includes("костюм") || cat.includes("комбинезон") || cat.includes("комплект") || cat.includes("set")) {
    return "set";
  }
  if (cat.includes("рубаш") || cat.includes("блуз") || cat.includes("shirt")) {
    return "shirt";
  }
  if (cat.includes("футболк") || cat.includes("майк") || cat.includes("топ") || cat.includes("t-shirt")) {
    return "t-shirt";
  }
  if (cat.includes("худи") || cat.includes("свитшот") || cat.includes("толстовк") || cat.includes("джемпер") || cat.includes("свитер") || cat.includes("пуловер") || cat.includes("кардиган") || cat.includes("hoodie")) {
    return "hoodie";
  }
  if (cat.includes("куртк") || cat.includes("пальто") || cat.includes("пиджак") || cat.includes("жилет") || cat.includes("ветровк") || cat.includes("бомбер") || cat.includes("jacket")) {
    return "jacket";
  }
  return "garment";
}

export interface ImageGenerationStatus {
  id?: string;
  status: string;
  progress: number;
  total: number;
  images?: Array<{
    image_id?: string;
    fileName: string;
    url: string;
    label?: string;
    pose?: string;
    output_type?: string;
    validation_result?: {
      image_id?: string;
      pose?: string;
      label?: string;
      validation_status?: "approved" | "warning" | "review_required" | "failed";
      validation_score?: number;
      risk_level?: "low" | "medium" | "high";
      warnings?: string[];
      dominant_delta_e?: number | null;
      palette_delta_e?: number | null;
      missing_details?: string[];
      can_use_for_listing?: boolean;
      retry_used?: boolean;
      pose_validation?: "pass" | "warning";
      expected_pose?: string | null;
      detected_pose?: string | null;
      realism_issues?: string[];
      manual_actions?: {
        hidden?: boolean;
        used_anyway?: boolean;
        approved_manually?: boolean;
        rejected_manually?: boolean;
      };
    };
  }>;
  error?: string | null;
  job_type?: string;
  seller_warning?: string | null;
  final_validation_status?: "approved" | "warning" | "review_required" | "failed" | string | null;
  validation_summary?: {
    total_images?: number;
    approved_count?: number;
    warning_count?: number;
    review_required_count?: number;
    failed_count?: number;
  } | null;
  quality_report?: {
    catalog_score?: number;
    best_thumbnail?: string;
    best_lifestyle_image?: string;
    best_marketing_banner?: string;
  } | null;
  failed_validations?: Array<{
    failed_pose?: string;
    failed_reason?: string;
    validation_score?: number;
    dominant_delta_e?: number;
    palette_delta_e?: number;
    missing_details?: string[];
    complex_product_mode?: boolean;
    final_validation_status?: string;
  }>;
}

export interface RecommendationPayload {
  recommendedModelGender?: string;
  recommendedBodyType?: string;
  recommendedAgeGroup?: string;
  recommendedEthnicity?: string;
  recommendedModelStyle?: string;
  recommendedBackground?: string;
}

const SUPPORTED_CATALOG_QUANTITIES = [3, 6, 8] as const;
const MAX_UPLOAD_IMAGE_BYTES = 10 * 1024 * 1024;

function normalizeCatalogQuantity(quantity: number): 3 | 6 | 8 {
  if (quantity <= 3) return 3;
  if (quantity <= 6) return 6;
  return 8;
}

function toMediaUrl(url?: string | null) {
  if (!url) return null;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  if (url.startsWith("/storage")) return publicAssetUrl(url);
  return `${API_BASE}${url.startsWith("/") ? url : `/${url}`}`;
}

interface GarmentJsonPayload {
  product_type?: string;
  garment_area?: string;
  main_color?: string;
  secondary_color?: string;
  color_palette?: string[];
  material?: string;
  category?: string;
  special_details?: string[];
  complex_product_mode?: boolean;
  front_view?: {
    key_details?: string[];
  };
}

interface MediaGalleryProps {
  variant?: VariantCardState;
  selectedPhotoIndex: number;
  draggedImageIndex: number | null;
  generationStatus?: ImageGenerationStatus;
  onSelectPhoto: (index: number) => void;
  onSetDraggedImageIndex: (index: number | null) => void;
  onAddImages: (files: FileList) => void;
  onGenerateImages: (input: {
    frontImage: File;
    backImage?: File;
    variantColorImage?: File;
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
    enableQualityCheck?: boolean;
  }) => void;
  onMoveImage: (fromIndex: number, toIndex: number) => void;
  onRemoveImage: (index: number) => void;
  onZoomImage: (file: File) => void;
  onJobUpdate?: (job: ImageGenerationStatus) => void;
  productCategory?: string;
  recommendations?: RecommendationPayload | null;
  draftId?: string | number;
  productReferenceImages?: File[];
  onUseReferenceImages?: () => void;
  useReferenceImagesLabel?: string;
}

export function MediaGallery({
  variant,
  selectedPhotoIndex,
  draggedImageIndex,
  generationStatus,
  onSelectPhoto,
  onSetDraggedImageIndex,
  onAddImages,
  onGenerateImages,
  onMoveImage,
  onRemoveImage,
  onZoomImage,
  onJobUpdate,
  productCategory = "",
  recommendations,
  draftId,
  productReferenceImages = [],
  onUseReferenceImages,
  useReferenceImagesLabel = "Use source photos",
}: MediaGalleryProps) {
  const { currentStoreId } = useStore();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [frontImage, setFrontImage] = useState<File | null>(null);
  const [backImage, setBackImage] = useState<File | null>(null);
  const [quantity, setQuantity] = useState(5);
  const [validationError, setValidationError] = useState("");
  const [selectedModelId, setSelectedModelId] = useState<string>("");
  const backgroundStyle = "studio";
  const [selectedImageModel, setSelectedImageModel] = useState<string>("gpt-image-2");
  const [enableQualityCheck, setEnableQualityCheck] = useState(true);
  const [customModelImage, setCustomModelImage] = useState<File | null>(null);
  const [modelSource, setModelSource] = useState<"my" | "system" | "upload">("my");
  const [isExporting, setIsExporting] = useState<Record<string, boolean>>({});
  const [models, setModels] = useState<RuntimeModelTemplate[]>([]);
  const [shopModels, setShopModels] = useState<ShopModel[]>([]);
  const [modelsLoadError, setModelsLoadError] = useState("");

  const [garmentJson, setGarmentJson] = useState<GarmentJsonPayload | null>(null);
  const [isFetchingGarment, setIsFetchingGarment] = useState(false);
  const [isAnalyzingGarment, setIsAnalyzingGarment] = useState(false);
  const [showJsonPreview, setShowJsonPreview] = useState(false);
  const [imageActionLoading, setImageActionLoading] = useState<string | null>(null);
  const baseFrontImage = productReferenceImages[0] || frontImage || null;
  const baseBackImage = productReferenceImages[1] || null;
  const effectiveFrontImage = baseFrontImage;
  const effectiveBackImage = baseBackImage;
  const variantColorImage = frontImage || null;

  useEffect(() => {
    let cancelled = false;

    fetchRuntimeModelTemplates()
      .then((items) => {
        if (cancelled) return;
        startTransition(() => {
          setModelsLoadError("");
          setModels(items);
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        startTransition(() => {
          setModels([]);
          setModelsLoadError(err instanceof Error ? err.message : "Failed to load model templates.");
        });
      });

    fetchRuntimeAiStudioSettings()
      .then((runtimeSettings) => {
        if (cancelled || !runtimeSettings) return;
        startTransition(() => {
          setQuantity(normalizeCatalogQuantity(runtimeSettings.default_quantity));
          setSelectedImageModel(runtimeSettings.default_image_model);
        });
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!currentStoreId) {
      startTransition(() => setShopModels([]));
      return;
    }
    let cancelled = false;
    fetchShopModels(currentStoreId)
      .then((items) => {
        if (cancelled) return;
        startTransition(() => {
          setShopModels(items);
          if (modelSource === "my") {
            setSelectedModelId(items[0]?.id || "");
          }
        });
      })
      .catch(() => {
        if (cancelled) return;
        startTransition(() => setShopModels([]));
      });
    return () => {
      cancelled = true;
    };
  }, [currentStoreId, modelSource]);

  useEffect(() => {
    if (!isModalOpen || !draftId) return;
    let cancelled = false;

    startTransition(() => setIsFetchingGarment(true));
    api.get(`/cards/drafts/${draftId}/garment`)
      .then((data) => {
        if (cancelled) return;
        startTransition(() => {
          setGarmentJson(data && typeof data === "object" && "product_type" in data ? data as GarmentJsonPayload : null);
        });
      })
      .catch((err) => {
        console.error("Error fetching garment json:", err);
        if (cancelled) return;
        startTransition(() => setGarmentJson(null));
      })
      .finally(() => {
        if (cancelled) return;
        startTransition(() => setIsFetchingGarment(false));
      });

    return () => {
      cancelled = true;
    };
  }, [isModalOpen, draftId]);
  const handleAnalyzeGarment = async () => {
    if (!effectiveFrontImage) {
      setValidationError("Front product image is required.");
      return;
    }
    setIsAnalyzingGarment(true);
    setValidationError("");
    try {
      const formData = new FormData();
      formData.append("front_image", effectiveFrontImage);
      if (effectiveBackImage) {
        formData.append("back_image", effectiveBackImage);
      }
      formData.append("category", productCategory);
      formData.append("title", variant?.title || "");
      formData.append("description", variant?.description || "");

      const data = await api.post(`/cards/drafts/${draftId}/garment/analyze`, formData);
      setGarmentJson(data as GarmentJsonPayload);
    } catch (err: unknown) {
      setValidationError(err instanceof Error ? err.message : "Failed to analyze garment");
    } finally {
      setIsAnalyzingGarment(false);
    }
  };

  const handleExport = async (marketplace: string) => {
    const jobId = generationStatus?.id;
    if (!draftId || !jobId) {
      alert("Draft ID or Job ID missing. Please make sure image generation completed successfully.");
      return;
    }
    
    setIsExporting(prev => ({ ...prev, [marketplace]: true }));
    try {
      const url = `${API_BASE}/cards/drafts/${draftId}/image-jobs/${jobId}/export/${marketplace}`;
      const response = await fetch(url, {
        method: "GET",
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Failed to export catalog package");
      }
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `${marketplace}_catalog_${jobId.slice(0, 8)}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      console.error("Export error:", err);
      alert("Failed to export package: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setIsExporting(prev => ({ ...prev, [marketplace]: false }));
    }
  };

  useEffect(() => {
    if (recommendations) {
      const recGender = recommendations.recommendedModelGender || "female";
      const recBodyType = (recommendations.recommendedBodyType || "").toLowerCase();
      const matchingModel = models.find(
        (m) => m.gender.toLowerCase() === recGender.toLowerCase() && m.bodyType.toLowerCase().replace(/\s+/g, "_") === recBodyType
      ) || models.find(
        (m) => m.gender.toLowerCase() === recGender.toLowerCase()
      );
      if (matchingModel) {
        startTransition(() => setSelectedModelId(matchingModel.id));
      }
    }
  }, [models, recommendations]);

  const images = variant?.images || [];
  const selectedImage = images[selectedPhotoIndex] || images[0] || null;
  const selectedGeneratedImage = generationStatus?.images?.find((item) => item.fileName === selectedImage?.name);

  const getProductGender = () => {
    if (!variant?.characteristics) return "";
    const charc = variant.characteristics.find(
      (c) => c.name.toLowerCase() === "пол" || c.name.toLowerCase() === "gender"
    );
    if (!charc) return "";
    const val = Array.isArray(charc.value) ? charc.value[0] : charc.value;
    return String(val || "").toLowerCase();
  };

  const productGender = getProductGender();
  const isFemaleProd = productGender.includes("жен") || productGender.includes("fem") || productGender.includes("girl") || productGender.includes("woman");
  const isMaleProd = productGender.includes("муж") || productGender.includes("маск") || productGender.includes("boy") || productGender.includes("man");

  const activeModels = modelSource === "my" ? shopModels : models;
  const selectedModel = activeModels.find((model) => model.id === selectedModelId);
  const isGenderMismatch = selectedModel && (
    (selectedModel.gender.toLowerCase() === "female" && isMaleProd) ||
    (selectedModel.gender.toLowerCase() === "male" && isFemaleProd)
  );

  const productGenderText = isFemaleProd ? "Female" : isMaleProd ? "Male" : productGender || "Unknown";
  const modelGenderText = selectedModel ? selectedModel.gender : "";
  const isGenerating = generationStatus?.status === "queued" || generationStatus?.status === "processing";
  const isGenerationCompleted = generationStatus?.status === "completed" || generationStatus?.status === "completed_with_warnings";

  const handleGeneratedImageAction = async (action: "use_anyway" | "hide" | "approve" | "reject") => {
    if (!draftId || !generationStatus?.id || !selectedGeneratedImage?.image_id) return;
    setImageActionLoading(action);
    try {
      const updatedJob = await api.post(
        `/cards/drafts/${draftId}/image-jobs/${generationStatus.id}/images/${selectedGeneratedImage.image_id}/actions`,
        { action }
      ) as ImageGenerationStatus;
      onJobUpdate?.(updatedJob);
      if (action === "hide") {
        onRemoveImage(selectedPhotoIndex);
      }
    } finally {
      setImageActionLoading(null);
    }
  };

  const handleRetryGeneratedImage = async () => {
    if (!draftId || !generationStatus?.id || !selectedGeneratedImage?.image_id) return;
    setImageActionLoading("retry");
    try {
      const nextJob = await api.post(
        `/cards/drafts/${draftId}/image-jobs/${generationStatus.id}/images/${selectedGeneratedImage.image_id}/retry`,
        {}
      ) as ImageGenerationStatus;
      onJobUpdate?.(nextJob);
    } finally {
      setImageActionLoading(null);
    }
  };

  const handleDownloadGeneratedImage = async () => {
    const url = toMediaUrl(selectedGeneratedImage?.url || "");
    if (!url) return;
    const link = document.createElement("a");
    link.href = url;
    link.download = selectedGeneratedImage?.fileName || "generated-image.jpg";
    link.target = "_blank";
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const validateImage = (file?: File | null) => {
    if (!file) return true;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setValidationError("Only JPG, PNG, or WEBP images are supported.");
      return false;
    }
    if (file.size > MAX_UPLOAD_IMAGE_BYTES) {
      setValidationError(`"${file.name}" exceeds the 10 MB upload limit.`);
      return false;
    }
    return true;
  };

  const selectFile = (fileList: FileList | null, setter: (file: File | null) => void) => {
    const file = fileList?.[0] || null;
    if (file && !validateImage(file)) {
      setter(null);
      return;
    }
    setValidationError("");
    setter(file);
  };

  const submit = () => {
    if (!effectiveFrontImage) {
      setValidationError("Front product image is required.");
      return;
    }
    if (modelSource === "upload") {
      if (!customModelImage) {
        setValidationError("Please upload a model reference image.");
        return;
      }
      if (!validateImage(effectiveFrontImage) || (effectiveBackImage && !validateImage(effectiveBackImage)) || !validateImage(customModelImage)) {
        setValidationError("Only JPG, PNG, or WEBP images are supported.");
        return;
      }
      onGenerateImages({
        frontImage: effectiveFrontImage,
        backImage: baseBackImage || undefined,
        variantColorImage: variantColorImage || undefined,
        modelImage: customModelImage,
        modelId: "none",
        backgroundStyle,
        quantity,
        jobType: "gpt_image_openai",
        productCategory,
        imageModel: selectedImageModel,
        autoGenerateModel: false,
        enableQualityCheck,
      });
    } else {
      if (!selectedModelId || selectedModelId === "none") {
        setValidationError("Please select a real model reference before generating catalog images.");
        return;
      }
      if (!validateImage(effectiveFrontImage) || (effectiveBackImage && !validateImage(effectiveBackImage))) {
        setValidationError("Only JPG, PNG, or WEBP images are supported.");
        return;
      }
      const chosenModel = activeModels.find((model) => model.id === selectedModelId);
      if (!chosenModel) {
        setValidationError("Please select a real model reference before generating catalog images.");
        return;
      }
      onGenerateImages({
        frontImage: effectiveFrontImage,
        backImage: baseBackImage || undefined,
        variantColorImage: variantColorImage || undefined,
        modelId: selectedModelId,
        selectedModelImageUrl: chosenModel.frontImageUrl,
        selectedModelGender: chosenModel.gender,
        selectedModelBodyType: chosenModel.bodyType,
        backgroundStyle,
        quantity,
        jobType: "gpt_image_openai",
        productCategory,
        imageModel: selectedImageModel,
        autoGenerateModel: false,
        enableQualityCheck,
      });
    }
    setIsModalOpen(false);
  };

  return (
    <aside className="h-fit rounded-xl border border-zinc-200 bg-white p-4 shadow-soft-sm xl:sticky xl:top-24">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-zinc-950">Photos</h2>
          {generationStatus?.quality_report?.catalog_score && (
            <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-bold text-indigo-750 border border-indigo-100 animate-scale-in">
              Score: {generationStatus.quality_report.catalog_score}/100
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setIsModalOpen(true)}
            disabled={!variant || isGenerating}
            isLoading={isGenerating}
          >
            <WandSparkles size={14} />
            Generate image
          </Button>
          <label className="inline-flex h-9 cursor-pointer items-center justify-center rounded-md border border-zinc-300 bg-white px-3 text-xs font-medium text-zinc-800 shadow-soft-sm transition-all duration-150 hover:bg-zinc-50 active:scale-[0.98]">
            <ImagePlus size={14} className="mr-2" /> Add
            <input
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(event) => {
                if (event.target.files) onAddImages(event.target.files);
                event.target.value = "";
              }}
            />
          </label>
          {onUseReferenceImages && productReferenceImages.length > 0 && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onUseReferenceImages}
              disabled={!variant}
            >
              <ImagePlus size={14} className="mr-2" /> {useReferenceImagesLabel}
            </Button>
          )}
        </div>
      </div>

      {isGenerating && (
        <div className="mb-3 rounded-lg border border-indigo-100 bg-indigo-50 px-3 py-2 text-xs text-indigo-700">
          <div className="mb-1 flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5">
              <Loader2 size={13} className="animate-spin" />
              Generating images
            </span>
            <span>{generationStatus?.progress || 0}/{generationStatus?.total || 0}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-indigo-100">
            <div
              className="h-full rounded-full bg-brand transition-all duration-300"
              style={{
                width: `${Math.round(((generationStatus?.progress || 0) / Math.max(generationStatus?.total || 1, 1)) * 100)}%`,
              }}
            />
          </div>
        </div>
      )}

      <div
        className="rounded-xl border-2 border-dashed border-zinc-300 bg-zinc-50/70 p-3 transition-colors duration-150"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          if (event.dataTransfer.files.length) onAddImages(event.dataTransfer.files);
        }}
      >
        {images.length ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-[72px_minmax(0,1fr)]">
            <div className="grid max-h-[180px] grid-cols-4 gap-2 overflow-y-auto pr-1 sm:block sm:max-h-[430px] sm:space-y-2">
              {images.map((image, index) => (
                <button
                  type="button"
                  key={`${image.name}-${index}`}
                  draggable
                  onClick={() => onSelectPhoto(index)}
                  onDragStart={(event) => {
                    event.dataTransfer.effectAllowed = "move";
                    onSetDraggedImageIndex(index);
                    onSelectPhoto(index);
                  }}
                  onDragOver={(event) => {
                    event.preventDefault();
                    event.dataTransfer.dropEffect = "move";
                  }}
                  onDrop={(event) => {
                    event.preventDefault();
                    if (draggedImageIndex !== null) onMoveImage(draggedImageIndex, index);
                    onSetDraggedImageIndex(null);
                  }}
                  onDragEnd={() => onSetDraggedImageIndex(null)}
                  className={`group relative aspect-[3/4] w-full cursor-grab overflow-hidden rounded-lg border bg-white transition-all duration-200 hover:-translate-y-0.5 hover:shadow-soft-md active:cursor-grabbing ${
                    selectedPhotoIndex === index ? "border-brand" : index === 0 ? "border-brand/60" : "border-zinc-200"
                  }`}
                >
                  <FilePreviewImage file={image} className="h-full w-full object-cover" alt="" onClick={(_, file) => onZoomImage(file)} />
                  <div className="absolute left-1 top-1 flex items-center gap-1 rounded-full bg-black/70 px-1.5 py-0.5 text-[10px] text-white">
                    <GripVertical size={11} /> {index === 0 ? "Cover" : index + 1}
                  </div>
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={(event) => {
                      event.stopPropagation();
                      onRemoveImage(index);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        event.stopPropagation();
                        onRemoveImage(index);
                      }
                    }}
                    className="absolute right-1 top-1 rounded-full bg-rose-600 p-1 text-white opacity-0 transition-opacity duration-150 group-hover:opacity-100"
                  >
                    <X size={12} />
                  </span>
                </button>
              ))}
            </div>

            <button
              type="button"
              className="group relative min-h-[300px] overflow-hidden rounded-lg border border-zinc-200 bg-white sm:min-h-[430px]"
            >
              <FilePreviewImage
                file={images[selectedPhotoIndex] || images[0]}
                className="h-full w-full object-contain transition-transform duration-300 group-hover:scale-[1.01]"
                alt=""
                onClick={(_, file) => onZoomImage(file)}
              />
              <div className="absolute left-3 top-3 rounded-full bg-black/70 px-2 py-1 text-[11px] text-white">
                {selectedPhotoIndex === 0 ? "Cover" : selectedPhotoIndex + 1}
              </div>
              {/* Badges */}
              {(() => {
                const currentImgName = (images[selectedPhotoIndex] || images[0])?.name;
                const qr = generationStatus?.quality_report;
                if (!qr) return null;
                
                const isThumb = qr.best_thumbnail === currentImgName;
                const isLife = qr.best_lifestyle_image === currentImgName;
                const isBanner = qr.best_marketing_banner === currentImgName;
                
                return (
                  <div className="absolute right-3 top-3 flex flex-col gap-1.5 items-end">
                    {isThumb && (
                      <span className="rounded-full bg-amber-500 px-2.5 py-1 text-[9px] font-bold text-white shadow-soft-sm uppercase tracking-wider animate-scale-in">
                        ⭐ Recommended Thumbnail
                      </span>
                    )}
                    {isLife && (
                      <span className="rounded-full bg-emerald-500 px-2.5 py-1 text-[9px] font-bold text-white shadow-soft-sm uppercase tracking-wider animate-scale-in">
                        ✨ Recommended Lifestyle Image
                      </span>
                    )}
                    {isBanner && (
                      <span className="rounded-full bg-indigo-500 px-2.5 py-1 text-[9px] font-bold text-white shadow-soft-sm uppercase tracking-wider animate-scale-in">
                        📢 Recommended Banner
                      </span>
                    )}
                  </div>
                );
              })()}
            </button>
          </div>
        ) : (
          <label className="flex min-h-[280px] cursor-pointer flex-col items-center justify-center rounded-lg text-center text-zinc-500 transition-colors duration-150 hover:text-brand">
            {isGenerating ? <Loader2 size={36} className="mb-3 animate-spin" /> : <ImagePlus size={36} className="mb-3" />}
            <span className="text-sm font-medium">Drop images here or click to upload</span>
            <input
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(event) => {
                if (event.target.files) onAddImages(event.target.files);
                event.target.value = "";
              }}
            />
          </label>
        )}
      </div>

      {selectedGeneratedImage ? (
        <div className="mt-4 space-y-3 rounded-xl border border-zinc-200 bg-zinc-50/80 p-3">
          <div className="text-xs font-semibold uppercase tracking-wider text-zinc-600">
            Generated image actions
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => void handleGeneratedImageAction("use_anyway")} isLoading={imageActionLoading === "use_anyway"}>
              Use image anyway
            </Button>
            <Button size="sm" variant="outline" onClick={() => void handleGeneratedImageAction("hide")} isLoading={imageActionLoading === "hide"}>
              Hide image
            </Button>
            <Button size="sm" variant="outline" onClick={() => void handleRetryGeneratedImage()} isLoading={imageActionLoading === "retry"}>
              Regenerate this image
            </Button>
            <Button size="sm" variant="outline" onClick={() => void handleDownloadGeneratedImage()}>
              Download image
            </Button>
            <Button size="sm" variant="outline" onClick={() => void handleGeneratedImageAction("approve")} isLoading={imageActionLoading === "approve"}>
              Mark as approved manually
            </Button>
          </div>
        </div>
      ) : null}

      {isGenerationCompleted && (
        <div className="mt-4 pt-4 border-t border-zinc-200 space-y-2.5 animate-fade-in">
          <h3 className="text-xs font-bold text-zinc-700 uppercase tracking-wider">Export Catalog Packages</h3>
          <div className="grid grid-cols-2 gap-2">
            {["wildberries", "ozon", "amazon", "shopify"].map((mp) => (
              <Button
                key={mp}
                type="button"
                variant="outline"
                size="sm"
                className="capitalize text-xs font-semibold"
                onClick={() => handleExport(mp)}
                disabled={isExporting[mp]}
                isLoading={isExporting[mp]}
              >
                {mp}
              </Button>
            ))}
          </div>
        </div>
      )}

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Generate AI Product Images" className="max-w-2xl">
        <div className="space-y-5">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            <div className="font-semibold">GPT-Image Catalog Workflow</div>
            <div className="mt-1 text-xs leading-relaxed text-emerald-800">
              This flow uses product-aware GPT-Image generation with garment JSON preservation, standard ecommerce poses, and post-generation validation.
            </div>
          </div>

          <div className="space-y-5">
              {!garmentJson ? (
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <ImageInput label="Front Product Image *" required file={productReferenceImages[0] || frontImage} onChange={(files) => selectFile(files, setFrontImage)} />
                    <ImageInput label="Back Product Image (Optional)" file={productReferenceImages[1] || backImage} onChange={(files) => selectFile(files, setBackImage)} />
                  </div>
                  {productReferenceImages.length > 0 && (
                    <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-600">
                      Đang dùng ảnh bạn đã nạp ban đầu để phân tích &amp; sinh ảnh. 2 ảnh này KHÔNG được đăng lên WB.
                    </div>
                  )}
                  {validationError && (
                    <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 animate-fade-in">
                      {validationError}
                    </div>
                  )}
                  <Button
                    type="button"
                    variant="brand"
                    className="w-full"
                    onClick={handleAnalyzeGarment}
                    isLoading={isAnalyzingGarment || isFetchingGarment}
                    disabled={!effectiveFrontImage}
                  >
                    Analyze Product Garment
                  </Button>
                </div>
              ) : (
                <div className="space-y-5 animate-in fade-in duration-300">
                  {/* Product Understanding */}
                  <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-4 space-y-3">
                    <div className="border-b border-zinc-200 pb-2">
                      <h3 className="text-sm font-bold text-zinc-800 uppercase tracking-wider">Product Understanding</h3>
                    </div>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                      <div>
                        <span className="font-semibold text-zinc-500 block mb-0.5">Product Type</span>
                        <span className="font-semibold text-zinc-800">{garmentJson.product_type}</span>
                      </div>
                      <div>
                        <span className="font-semibold text-zinc-500 block mb-0.5">Garment Area</span>
                        <span className="font-semibold text-zinc-800 capitalize">
                          {garmentJson.garment_area?.replace("_", " ")}
                        </span>
                      </div>
                      <div>
                        <span className="font-semibold text-zinc-500 block mb-0.5">Main Color</span>
                        <span className="font-semibold text-zinc-800 capitalize">{garmentJson.main_color}</span>
                      </div>
                      <div>
                        <span className="font-semibold text-zinc-500 block mb-0.5">Material</span>
                        <span className="font-semibold text-zinc-800 capitalize">{garmentJson.material}</span>
                      </div>
                    </div>
                    {garmentJson.front_view?.key_details && (
                      <div className="text-xs pt-1 border-t border-zinc-200">
                        <span className="font-semibold text-zinc-500 block mb-0.5">Key Details</span>
                        <span className="text-zinc-700 leading-relaxed">
                          {garmentJson.front_view.key_details.join(", ")}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Warning if product category is uncertain */}
                  {(() => {
                    const uncertain = !garmentJson.category || 
                      garmentJson.category.toLowerCase().includes("unknown") || 
                      (productCategory && !productCategory.toLowerCase().includes(garmentJson.category.toLowerCase()) && !garmentJson.category.toLowerCase().includes(productCategory.toLowerCase()));
                    if (uncertain) {
                      return (
                        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-800 flex items-start gap-2.5 animate-fade-in">
                          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-4 w-4 shrink-0 text-amber-600 mt-0.5">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                          </svg>
                          <span>
                            <strong>Uncertain Product Category:</strong> The analyzed category ({garmentJson.category || "None"}) differs from the card category ({productCategory || "None"}). Prompt matching may not be optimal.
                          </span>
                        </div>
                      );
                    }
                    return null;
                  })()}

                  {garmentJson.complex_product_mode && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-800 flex items-start gap-2.5 animate-fade-in">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-4 w-4 shrink-0 text-amber-600 mt-0.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                      </svg>
                      <span>
                        <strong>Complex garment detected:</strong> rhinestones/distressing/logos may be harder to preserve. Strict product mode will be used.
                      </span>
                    </div>
                  )}

                  <div className="rounded-xl border border-sky-200 bg-sky-50/70 p-4 space-y-3">
                    <div>
                      <h3 className="text-sm font-bold text-sky-950">Variant Color Reference</h3>
                      <p className="mt-1 text-xs leading-relaxed text-sky-800">
                        For another color of the same article, upload one real photo of that color here. The system keeps the original garment structure and analyzes only this variant color.
                      </p>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-1">
                      <ImageInput
                        label="Variant color image"
                        file={frontImage}
                        onChange={(files) => selectFile(files, setFrontImage)}
                      />
                    </div>
                    {!frontImage && productReferenceImages[0] && (
                      <div className="rounded-lg border border-sky-200 bg-white px-3 py-2 text-xs text-sky-800">
                        No variant color image selected. The original product photo will be reused.
                      </div>
                    )}
                  </div>

                  {/* Shop, system, and one-time upload model sources */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-zinc-800">Model Source</label>
                    <div className="grid grid-cols-3 gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setModelSource("my");
                          setSelectedModelId(shopModels[0]?.id || "");
                        }}
                        className={`flex-1 rounded-lg py-2 text-xs font-semibold border transition-all duration-150 ${
                          modelSource === "my"
                            ? "bg-brand border-brand text-white shadow-soft-sm"
                            : "bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50"
                        }`}
                      >
                        My Models
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setModelSource("system");
                          setSelectedModelId(models[0]?.id || "");
                        }}
                        className={`flex-1 rounded-lg py-2 text-xs font-semibold border transition-all duration-150 ${
                          modelSource === "system"
                            ? "bg-brand border-brand text-white shadow-soft-sm"
                            : "bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50"
                        }`}
                      >
                        System Models
                      </button>
                      <button
                        type="button"
                        onClick={() => setModelSource("upload")}
                        className={`flex-1 rounded-lg py-2 text-xs font-semibold border transition-all duration-150 ${
                          modelSource === "upload"
                            ? "bg-brand border-brand text-white shadow-soft-sm"
                            : "bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50"
                        }`}
                      >
                        Upload Model
                      </button>
                    </div>
                  </div>

                  {modelSource === "upload" ? (
                    <div className="w-full">
                      <ImageInput
                        label="Model Reference Image *"
                        required
                        file={customModelImage}
                        onChange={(files) => selectFile(files, setCustomModelImage)}
                      />
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {modelSource === "system" && modelsLoadError && (
                        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                          {modelsLoadError}
                        </div>
                      )}
                      {modelSource === "my" && shopModels.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-sky-300 bg-sky-50 px-4 py-6 text-center text-sm text-sky-800">
                          Shop này chưa có model riêng. Hãy thêm model từ mục <strong>My Models</strong> ở trang Home.
                        </div>
                      ) : (
                        <ModelSelector
                          selectedModelId={selectedModelId}
                          models={activeModels}
                          onSelectModel={(model) => {
                            setSelectedModelId(model.id);
                            setValidationError("");
                          }}
                        />
                      )}
                    </div>
                  )}

                  {/* Garment JSON preview */}
                  <div>
                    <button
                      type="button"
                      onClick={() => setShowJsonPreview(!showJsonPreview)}
                      className="text-xs text-zinc-500 hover:text-brand underline font-medium flex items-center gap-1 focus:outline-none"
                    >
                      {showJsonPreview ? "Hide" : "Show"} Garment JSON Preview
                    </button>
                    {showJsonPreview && (
                      <pre className="mt-2 text-[10px] bg-zinc-900 text-zinc-200 p-3 rounded-lg overflow-x-auto max-h-40 leading-relaxed font-mono">
                        {JSON.stringify(garmentJson, null, 2)}
                      </pre>
                    )}
                  </div>

                  {isGenderMismatch && modelSource !== "upload" && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-3 text-xs text-amber-800 flex items-start gap-2.5">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-4 w-4 shrink-0 text-amber-600 mt-0.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                      </svg>
                      <div>
                        <span className="font-semibold">Gender Mismatch Warning:</span> Product&apos;s gender ({productGenderText}) does not match the selected model&apos;s gender ({modelGenderText}). This might cause fit mapping distortions on the model.
                      </div>
                    </div>
                  )}

                  {selectedModel?.isAiGenerated && modelSource === "system" && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-3 text-xs text-amber-800 flex items-start gap-2.5 animate-fade-in">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-4 w-4 shrink-0 text-amber-600 mt-0.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                      </svg>
                      <div>
                        If selected model reference is AI-generated, image may look less realistic. Real photographed model templates produce better results.
                      </div>
                    </div>
                  )}

                  {/* Seller review warning */}
                  <div className="rounded-lg border border-blue-200 bg-blue-50 px-3.5 py-3 text-xs text-blue-800 flex items-start gap-2.5 animate-fade-in">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-4 w-4 shrink-0 text-blue-600 mt-0.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 111.086.797l-.535.536a.75.75 0 01-1.06 0l-.536-.536a.75.75 0 010-1.06zm1.25 2.25a.75.75 0 100-1.5.75.75 0 000 1.5zM12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25z" />
                    </svg>
                    <span>
                      Please review AI-generated images before publishing. Logos, text and complex patterns may require manual approval.
                    </span>
                  </div>

                  <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-700">
                    <div className="font-semibold text-zinc-900">Pose Bundle Preview</div>
                    <div className="mt-1 leading-relaxed">
                      {quantity === 3 && "Front, Lifestyle, Detail"}
                      {quantity === 6 && (baseBackImage
                        ? "Front, Side, Back, Lifestyle, Detail, Banner"
                        : "Front, Side, Lifestyle, Detail, Extra Detail, Banner")}
                      {quantity === 8 && (baseBackImage
                        ? "Front, Side, Back, Walking, Hand On Hip, Sitting, Fabric Detail, Banner"
                        : "Front, Side, Walking, Hand On Hip, Sitting, Fabric Detail, Product Detail, Banner")}
                    </div>
                    <div className="mt-2 text-[11px] text-zinc-500">
                      Back view is generated only when a back product image is uploaded.
                      {!baseBackImage && quantity > 3 && (
                        <span className="block mt-0.5 text-amber-600 font-medium">
                          Note: Back view will be replaced by {quantity === 6 ? "Extra Detail" : "Product Detail"} shot.
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}
          </div>

          {!garmentJson ? null : (
            <>
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
                <label className="mb-2 block text-sm font-medium text-zinc-800">Generated images</label>
                <div className="grid grid-cols-4 gap-2">
                  {SUPPORTED_CATALOG_QUANTITIES.map((qty) => (
                    <button
                      key={qty}
                      type="button"
                      onClick={() => setQuantity(qty)}
                      className={`rounded-lg py-2 text-sm font-medium border transition-all duration-150 ${
                        quantity === qty
                          ? "bg-brand border-brand text-white shadow-soft-sm"
                          : "bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50"
                      }`}
                    >
                      {qty} Images
                    </button>
                  ))}
                </div>
              </div>

              <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-zinc-200 bg-white p-4">
                <input
                  type="checkbox"
                  checked={enableQualityCheck}
                  onChange={(event) => setEnableQualityCheck(event.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-zinc-300 text-brand focus:ring-brand"
                />
                <span>
                  <span className="block text-sm font-semibold text-zinc-900">Kiểm tra và tự sửa ảnh bằng Gemini</span>
                  <span className="mt-1 block text-xs leading-relaxed text-zinc-500">
                    Bật: kiểm tra chất lượng và tự sửa tối đa một ảnh chưa đạt. Tắt: ảnh nào tạo xong sẽ hiện ngay, không chờ kiểm tra.
                  </span>
                </span>
              </label>

              {validationError && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                  {validationError}
                </div>
              )}

              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                <Button variant="outline" onClick={() => setIsModalOpen(false)}>Cancel</Button>
                <Button variant="brand" onClick={submit}>
                  <WandSparkles size={16} />
                  Generate
                </Button>
              </div>
            </>
          )}
        </div>
      </Modal>
    </aside>
  );
}

function ImageInput({
  label,
  required,
  file,
  onChange,
}: {
  label: string;
  required?: boolean;
  file: File | null;
  onChange: (files: FileList | null) => void;
}) {
  return (
    <label className="group flex min-h-40 cursor-pointer flex-col overflow-hidden rounded-lg border border-dashed border-zinc-300 bg-white text-center transition-colors hover:border-brand hover:bg-indigo-50/40">
      {file ? (
        <div className="relative h-32 w-full bg-zinc-100">
          <FilePreviewImage file={file} className="h-full w-full object-contain p-1" alt={label} />
          <div className="absolute inset-x-0 bottom-0 bg-black/65 px-2 py-1 text-[11px] text-white opacity-0 transition-opacity group-hover:opacity-100">
            Click to replace
          </div>
        </div>
      ) : (
        <div className="flex h-32 flex-col items-center justify-center p-3">
          <ImagePlus size={24} className="mb-2 text-zinc-400" />
          <span className="text-xs text-zinc-500">JPG, PNG, WEBP</span>
        </div>
      )}
      <div className="flex min-h-14 flex-col justify-center px-3 py-2">
        <span className="text-sm font-medium text-zinc-800">
          {label} {required && <span className="text-brand">*</span>}
        </span>
        {file && <span className="mt-1 line-clamp-1 text-xs text-zinc-500">{file.name}</span>}
      </div>
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(event) => {
          onChange(event.target.files);
          event.target.value = "";
        }}
      />
    </label>
  );
}
