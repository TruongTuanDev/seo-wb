"use client";

import { CategorySelector } from "@/components/cards/CategorySelector";
import { CharacteristicsEditor, Characteristic } from "@/components/cards/CharacteristicsEditor";
import { SizeTable, SizeRow } from "@/components/cards/SizeTable";
import type { PackageDimensions, VariantCardState } from "@/components/cards/types";
import { Input } from "@/components/ui/Input";
import { useLanguage } from "@/contexts/LanguageContext";

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
  const { t } = useLanguage();
  return (
    <section className="space-y-6">
      <div className="space-y-5 rounded-xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
        <div className="flex items-start justify-between gap-4 border-b border-zinc-200 pb-4">
          <h2 className="text-lg font-semibold text-zinc-950">{t("pdfMainInfo")}</h2>
          <span className="max-w-full truncate rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-xs text-zinc-500">
            {subjectName || t("cselSubject")} / {effectiveBrand()}
          </span>
        </div>

        <Input
          label={t("pdfTitle")}
          value={activeVariant?.title || ""}
          onChange={(event) => onUpdateVariant({ title: event.target.value })}
          placeholder={t("pdfTitlePh")}
        />

        <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-4">
          <CategorySelector
            storeId={storeId}
            selectedSubjectId={subjectId || undefined}
            selectedSubjectName={subjectName || undefined}
            onSubjectSelected={onSetSubject}
            shopCatalogOnly
          />
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Input
            label={t("pdfColor")}
            value={activeVariant?.color || ""}
            onChange={(event) => onSetActiveColor(event.target.value)}
            placeholder={t("pdfColorPh")}
          />
          <Input
            label={t("pdfMaterial")}
            value={getCharacteristicValue(["Состав", "composition", "material"])}
            onChange={(event) => setCharacteristicValue(["Состав", "composition", "material"], event.target.value)}
            placeholder={t("pdfMaterialPh")}
          />
          <Input
            label={t("pdfGender")}
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
              label={t("pdfVendorCode")}
              value={activeVariant?.vendorCode || ""}
              onChange={(event) => onUpdateVariant({ vendorCode: event.target.value })}
              error={fieldErrors[`${activeVariant?.id}.vendorCode`]}
            />
          </div>
          <Input label={t("pdfBrand")} value={brand} onChange={(event) => onSetBrand(event.target.value)} placeholder={t("pdfBrandPh")} />
        </div>

        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <label className="font-medium text-zinc-700">{t("pdfDescription")}</label>
            <span className="text-zinc-500">{activeVariant?.description.length || 0} {t("pdfCharsUnit")}</span>
          </div>
          <textarea
            value={activeVariant?.description || ""}
            onChange={(event) => onUpdateVariant({ description: event.target.value })}
            className="h-[220px] w-full resize-none rounded-md border border-zinc-300 bg-white p-3 text-sm text-zinc-900 shadow-soft-sm transition-colors duration-150 placeholder:text-zinc-400 focus:border-brand focus:outline-none focus:ring-2 focus:ring-indigo-100"
          />
        </div>
      </div>

      <div className="space-y-5 rounded-xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
        <h2 className="text-lg font-semibold text-zinc-950">{t("pdfChars")}</h2>
        <CharacteristicsEditor
          storeId={storeId}
          subjectId={subjectId}
          characteristics={activeVariant?.characteristics || []}
          onChange={(nextCharcs: Characteristic[]) => onUpdateVariant({ characteristics: nextCharcs })}
        />
      </div>

      <div className="space-y-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
        <h2 className="text-lg font-semibold text-zinc-950">{t("pdfSizes")}</h2>
        <SizeTable
          sizes={activeVariant?.sizes || []}
          onChange={(nextSizes: SizeRow[]) => onUpdateVariant({ sizes: nextSizes })}
        />
      </div>

      <div className="space-y-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-soft-sm">
        <h2 className="text-lg font-semibold text-zinc-950">{t("pdfPackage")}</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Input
            label={t("pdfLength")}
            type="number"
            value={dimensions.length}
            onChange={(event) => onSetDimensions({ ...dimensions, length: Number(event.target.value) })}
          />
          <Input
            label={t("pdfWidth")}
            type="number"
            value={dimensions.width}
            onChange={(event) => onSetDimensions({ ...dimensions, width: Number(event.target.value) })}
          />
          <Input
            label={t("pdfHeight")}
            type="number"
            value={dimensions.height}
            onChange={(event) => onSetDimensions({ ...dimensions, height: Number(event.target.value) })}
          />
          <Input
            label={t("pdfWeight")}
            type="number"
            value={dimensions.weightBrutto}
            onChange={(event) => onSetDimensions({ ...dimensions, weightBrutto: Number(event.target.value) })}
          />
        </div>
      </div>
    </section>
  );
}
