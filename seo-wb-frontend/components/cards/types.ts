import type { Characteristic } from "@/components/cards/CharacteristicsEditor";
import type { SizeRow } from "@/components/cards/SizeTable";

export interface VariantCardState {
  id: string;
  title: string;
  description: string;
  vendorCode: string;
  color: string;
  images: File[];
  characteristics: Characteristic[];
  sizes: SizeRow[];
}

export interface PackageDimensions {
  length: number;
  width: number;
  height: number;
  weightBrutto: number;
}
