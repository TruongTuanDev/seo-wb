import { api } from "@/lib/api";
import type { RuntimeModelTemplate } from "@/lib/modelTemplates";

export interface ShopModel extends RuntimeModelTemplate {
  storeId: number;
  garmentType?: string;
  createdAt?: string;
}

interface RawShopModel {
  id: string;
  store_id: number;
  name: string;
  gender?: string;
  body_type?: string;
  height_cm?: number | null;
  weight_kg?: number | null;
  garment_type?: string | null;
  reference_image_url: string;
  poses?: Record<string, string>;
  created_at?: string;
}

export async function fetchShopModels(storeId: number): Promise<ShopModel[]> {
  const response = await api.get(`/shop-models?store_id=${storeId}`);
  if (!Array.isArray(response)) return [];
  return response.map((item) => normalizeShopModel(item as RawShopModel));
}

export function normalizeShopModel(item: RawShopModel): ShopModel {
  const gender = normalizeGender(item.gender);
  const frontImageUrl = item.reference_image_url;
  return {
    id: item.id,
    storeId: item.store_id,
    name: item.name,
    gender,
    bodyType: item.body_type || "Unknown",
    height: Number(item.height_cm || 0),
    weight: Number(item.weight_kg || 0),
    frontImageUrl,
    imageUrl: frontImageUrl,
    label: item.name,
    description: [item.height_cm ? `${item.height_cm} cm` : "", item.weight_kg ? `${item.weight_kg} kg` : ""].filter(Boolean).join(" / "),
    availablePoses: Object.keys(item.poses || { front: frontImageUrl }),
    isAiGenerated: false,
    garmentType: item.garment_type || undefined,
    createdAt: item.created_at,
  };
}

function normalizeGender(value?: string): "Female" | "Male" | "Unknown" {
  const normalized = (value || "").trim().toLowerCase();
  if (normalized === "female") return "Female";
  if (normalized === "male") return "Male";
  return "Unknown";
}
