import { api } from "@/lib/api";
import { VTON_MODELS } from "@/lib/vtonModels";

export interface RuntimeModelTemplate {
  id: string;
  name: string;
  gender: "Female" | "Male" | "Unknown";
  bodyType: string;
  height: number;
  weight: number;
  frontImageUrl: string;
  imageUrl: string;
  label: string;
  description: string;
  availablePoses?: string[];
  isAiGenerated?: boolean;
  garmentType?: string | null;
}

interface RawRuntimeModelTemplate {
  id?: string;
  name?: string;
  gender?: "Female" | "Male" | "Unknown" | string;
  bodyType?: string;
  height?: number;
  weight?: number;
  frontImageUrl?: string;
  front_template?: string;
  imageUrl?: string;
  label?: string;
  description?: string;
  availablePoses?: string[];
  isAiGenerated?: boolean;
  garmentType?: string | null;
  garment_type?: string | null;
}

export interface RuntimeAiStudioSettings {
  default_image_model: string;
  default_quantity: number;
  max_retry: number;
  realism_threshold: number;
  validation_threshold: number;
  validation_failure_behavior: "block" | "warn";
  allow_legacy_vton: boolean;
}

export async function fetchRuntimeModelTemplates(): Promise<RuntimeModelTemplate[]> {
  try {
    const response = await api.get("/models");
    if (Array.isArray(response) && response.length > 0) {
      return response
        .map((item) => normalizeRuntimeModelTemplate(item as RawRuntimeModelTemplate))
        .filter((item): item is RuntimeModelTemplate => item !== null);
    }
  } catch {
    if (process.env.NODE_ENV === "production") {
      throw new Error("Runtime model templates are unavailable.");
    }
  }
  return process.env.NODE_ENV === "production"
    ? []
    : VTON_MODELS.map((item) => normalizeRuntimeModelTemplate(item)).filter((item): item is RuntimeModelTemplate => item !== null);
}

export async function fetchRuntimeAiStudioSettings(): Promise<RuntimeAiStudioSettings | null> {
  try {
    const response = await api.get("/settings/ai/runtime");
    return response as RuntimeAiStudioSettings;
  } catch {
    return null;
  }
}

function normalizeRuntimeModelTemplate(item: RawRuntimeModelTemplate): RuntimeModelTemplate | null {
  if (!item?.id || !item?.name) {
    return null;
  }
  const frontImageUrl = normalizeModelImageUrl(item.frontImageUrl || item.front_template || item.imageUrl || "");
  return {
    id: item.id,
    name: item.name,
    gender: normalizeGender(item.gender),
    bodyType: item.bodyType || "Unknown",
    height: Number(item.height || 0),
    weight: Number(item.weight || 0),
    frontImageUrl,
    imageUrl: normalizeModelImageUrl(item.imageUrl || frontImageUrl),
    label: item.label || item.name,
    description: item.description || item.name,
    availablePoses: Array.isArray(item.availablePoses) ? item.availablePoses : undefined,
    isAiGenerated: Boolean(item.isAiGenerated),
    garmentType: item.garmentType || item.garment_type || "full_body",
  };
}

function normalizeGender(value?: string): "Female" | "Male" | "Unknown" {
  const normalized = (value || "").trim().toLowerCase();
  if (normalized === "female") return "Female";
  if (normalized === "male") return "Male";
  return "Unknown";
}

function normalizeModelImageUrl(url: string): string {
  if (url === "/models/model1.png") {
    return "/models/model1.JPG";
  }
  return url;
}
