"use client";

import React, { useEffect } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { financeApi } from "@/lib/finance-api";
import { useLanguage } from "@/contexts/LanguageContext";
import { useToast } from "@/contexts/ToastContext";
import type { SellerFinanceSettings } from "@/lib/types/finance";

interface SellerSettingsFormData {
  tax_percent: string;
}

interface SellerFinanceSettingsFormProps {
  storeId: number;
  settings: SellerFinanceSettings | null;
  isLoading: boolean;
  onSaved: (updated: SellerFinanceSettings) => void;
}

export function SellerFinanceSettingsForm({
  storeId,
  settings,
  isLoading,
  onSaved,
}: SellerFinanceSettingsFormProps) {
  const { t } = useLanguage();
  const { success, error } = useToast();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<SellerSettingsFormData>();

  useEffect(() => {
    if (settings) {
      reset({
        tax_percent: String(Number(settings.defaultTaxRate ?? "0") * 100),
      });
    }
  }, [settings, reset]);

  const onSubmit = async (data: SellerSettingsFormData) => {
    try {
      const normalizedTaxRate = String((Number(data.tax_percent || "0") / 100).toFixed(4));
      const updated = await financeApi.updateSellerSettings(storeId, {
        currency: settings?.currency ?? "RUB",
        default_tax_mode: settings?.defaultTaxMode ?? "percent",
        tax_base: settings?.taxBase ?? "profit",
        default_packaging_cost: settings?.defaultPackagingCost ?? "0",
        default_labeling_cost: settings?.defaultLabelingCost ?? "0",
        default_shipping_to_warehouse_cost: settings?.defaultShippingToWarehouseCost ?? "0",
        default_other_unit_cost: settings?.defaultOtherUnitCost ?? "0",
        default_tax_rate: normalizedTaxRate,
      });
      onSaved(updated);
      success(t("save"), t("settingsSaved"));
    } catch (err) {
      error(t("error"), err instanceof Error ? err.message : "Unknown error");
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="flex flex-col gap-1.5">
            <div className="shimmer h-3 w-32 rounded" />
            <div className="shimmer h-10 w-full rounded-md" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="grid grid-cols-1 gap-4">
        <Input
          label={t("taxPercent")}
          type="number"
          step="0.01"
          min="0"
          max="100"
          placeholder="6"
          error={errors.tax_percent?.message}
          {...register("tax_percent", {
            required: "Required",
            min: { value: 0, message: "Must be >= 0" },
            max: { value: 100, message: "Must be <= 100" },
          })}
        />
      </div>

      <p className="rounded-lg bg-zinc-50 px-3 py-2 text-xs text-zinc-500">
        {t("taxPercentHelp")}
      </p>

      <Button type="submit" variant="brand" isLoading={isSubmitting} disabled={isSubmitting}>
        {t("save")}
      </Button>
    </form>
  );
}
