"use client";

import { CategorySelector } from "@/components/cards/CategorySelector";
import { CharacteristicsEditor, Characteristic } from "@/components/cards/CharacteristicsEditor";
import { SizeTable, SizeRow } from "@/components/cards/SizeTable";
import type { PackageDimensions, VariantCardState } from "@/components/cards/types";
import { Input } from "@/components/ui/Input";

interface ProductDetailsFormProps {
  storeId: number;
  subjectId: number;
  subjectName: string;
  brand: string;
  gender: string;
  dimensions: PackageDimensions;
  activeVariant?: VariantCardState;
  fieldErrors: Record<string, string>;
  effectiveBrand: () => string;
  onSetSubject: (id: number, name: string) => Promise<void> | void;
  onSetBrand: (value: string) => void;
  onSetGender: (value: string) => void;
  onSetDimensions: (value: PackageDimensions) => void;
  onUpdateVariant: (patch: Partial<VariantCardState>) => void;
  onSetActiveColor: (value: string) => void;
  getCharacteristicValue: (names: string[]) => string;
  setCharacteristicValue: (names: string[], value: string) => void;
}

export function ProductDetailsForm({
  storeId,
  subjectId,
  subjectName,
  brand,
  gender,
  dimensions,
  activeVariant,
  fieldErrors,
  effectiveBrand,
  onSetSubject,
  onSetBrand,
  onSetGender,
  onSetDimensions,
  onUpdateVariant,
  onSetActiveColor,
  getCharacteristicValue,
  setCharacteristicValue,
}: ProductDetailsFormProps) {
  return (
    <section className="space-y-6">
      <div className="space-y-5 rounded-xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
        <div className="flex items-start justify-between gap-4 border-b border-zinc-200 pb-4">
          <h2 className="text-lg font-semibold text-zinc-950">Main Information</h2>
          <span className="max-w-full truncate rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-xs text-zinc-500">
            {subjectName || "Subject"} / {effectiveBrand()}
          </span>
        </div>

        <Input
          label="Title"
          value={activeVariant?.title || ""}
          onChange={(event) => onUpdateVariant({ title: event.target.value })}
          placeholder="Наименование товара"
        />

        <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-4">
          <CategorySelector
            storeId={storeId}
            selectedSubjectId={subjectId || undefined}
            selectedSubjectName={subjectName || undefined}
            onSubjectSelected={onSetSubject}
          />
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Input
            label="Color"
            value={activeVariant?.color || ""}
            onChange={(event) => onSetActiveColor(event.target.value)}
            placeholder="черный"
          />
          <Input
            label="Material / Состав"
            value={getCharacteristicValue(["Состав", "composition", "material"])}
            onChange={(event) => setCharacteristicValue(["Состав", "composition", "material"], event.target.value)}
            placeholder="хлопок"
          />
          <Input
            label="Gender / Пол"
            value={getCharacteristicValue(["Пол", "gender"]) || gender}
            onChange={(event) => {
              onSetGender(event.target.value);
              setCharacteristicValue(["Пол", "gender"], event.target.value);
            }}
          />
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div id="field-vendorCode">
            <Input
              label="Vendor Code"
              value={activeVariant?.vendorCode || ""}
              onChange={(event) => onUpdateVariant({ vendorCode: event.target.value })}
              error={fieldErrors[`${activeVariant?.id}.vendorCode`]}
            />
          </div>
          <Input label="Brand" value={brand} onChange={(event) => onSetBrand(event.target.value)} placeholder="Нет бренда" />
        </div>

        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <label className="font-medium text-zinc-700">Description</label>
            <span className="text-zinc-500">{activeVariant?.description.length || 0} chars</span>
          </div>
          <textarea
            value={activeVariant?.description || ""}
            onChange={(event) => onUpdateVariant({ description: event.target.value })}
            className="h-[220px] w-full resize-none rounded-md border border-zinc-300 bg-white p-3 text-sm text-zinc-900 shadow-soft-sm transition-colors duration-150 placeholder:text-zinc-400 focus:border-brand focus:outline-none focus:ring-2 focus:ring-indigo-100"
          />
        </div>
      </div>

      <div className="space-y-5 rounded-xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
        <h2 className="text-lg font-semibold text-zinc-950">Important Characteristics</h2>
        <CharacteristicsEditor
          storeId={storeId}
          subjectId={subjectId}
          characteristics={activeVariant?.characteristics || []}
          onChange={(nextCharcs: Characteristic[]) => onUpdateVariant({ characteristics: nextCharcs })}
        />
      </div>

      <div className="space-y-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
        <h2 className="text-lg font-semibold text-zinc-950">Sizes & Barcodes</h2>
        <SizeTable
          sizes={activeVariant?.sizes || []}
          onChange={(nextSizes: SizeRow[]) => onUpdateVariant({ sizes: nextSizes })}
        />
      </div>

      <div className="space-y-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
        <h2 className="text-lg font-semibold text-zinc-950">Package</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Input
            label="Length (cm) *"
            type="number"
            value={dimensions.length}
            onChange={(event) => onSetDimensions({ ...dimensions, length: Number(event.target.value) })}
          />
          <Input
            label="Width (cm) *"
            type="number"
            value={dimensions.width}
            onChange={(event) => onSetDimensions({ ...dimensions, width: Number(event.target.value) })}
          />
          <Input
            label="Height (cm) *"
            type="number"
            value={dimensions.height}
            onChange={(event) => onSetDimensions({ ...dimensions, height: Number(event.target.value) })}
          />
          <Input
            label="Weight (kg) *"
            type="number"
            value={dimensions.weightBrutto}
            onChange={(event) => onSetDimensions({ ...dimensions, weightBrutto: Number(event.target.value) })}
          />
        </div>
      </div>
    </section>
  );
}
