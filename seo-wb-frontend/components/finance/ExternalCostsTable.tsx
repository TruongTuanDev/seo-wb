"use client";

import React, { useState } from "react";
import { Plus, Edit2, Trash2, ChevronLeft, ChevronRight } from "lucide-react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { formatMoney, formatDate } from "@/lib/finance-utils";
import { financeApi } from "@/lib/finance-api";
import { useToast } from "@/contexts/ToastContext";
import type { ExternalCost } from "@/lib/types/finance";

interface ExternalCostFormData {
  cost_date: string;
  period_from: string;
  period_to: string;
  cost_type: string;
  amount: string;
  currency: string;
  allocation_method: string;
  note: string;
}

const COST_TYPES = ["ads", "salary", "rent", "shipping", "packaging", "other"];
const ALLOCATION_METHODS = ["BY_REVENUE", "BY_QUANTITY", "EQUAL", "MANUAL"];

interface ExternalCostsTableProps {
  storeId: number;
  items: ExternalCost[];
  total: number;
  page: number;
  perPage: number;
  isLoading: boolean;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
}

export function ExternalCostsTable({
  storeId,
  items,
  total,
  page,
  perPage,
  isLoading,
  onPageChange,
  onRefresh,
}: ExternalCostsTableProps) {
  const { success, error } = useToast();
  const [editItem, setEditItem] = useState<ExternalCost | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [deleteItem, setDeleteItem] = useState<ExternalCost | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const totalPages = Math.ceil(total / perPage);

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } =
    useForm<ExternalCostFormData>({
      defaultValues: {
        currency: "RUB",
        allocation_method: "BY_REVENUE",
        cost_type: "ads",
      },
    });

  const openCreate = () => {
    setEditItem(null);
    reset({
      cost_date: new Date().toISOString().slice(0, 10),
      period_from: "",
      period_to: "",
      cost_type: "ads",
      amount: "",
      currency: "RUB",
      allocation_method: "BY_REVENUE",
      note: "",
    });
    setIsCreateOpen(true);
  };

  const openEdit = (item: ExternalCost) => {
    setEditItem(item);
    reset({
      cost_date: item.costDate,
      period_from: item.periodFrom,
      period_to: item.periodTo,
      cost_type: item.costType,
      amount: item.amount,
      currency: item.currency,
      allocation_method: item.allocationMethod,
      note: item.note ?? "",
    });
    setIsCreateOpen(true);
  };

  const onSave = async (data: ExternalCostFormData) => {
    try {
      const body = data as unknown as Record<string, string | number | null>;
      if (editItem) {
        await financeApi.updateExternalCost(storeId, editItem.id, body);
        success("Updated", "External cost updated.");
      } else {
        await financeApi.createExternalCost(storeId, body);
        success("Created", "External cost added.");
      }
      setIsCreateOpen(false);
      onRefresh();
    } catch (err) {
      error("Save failed", err instanceof Error ? err.message : "Unknown error");
    }
  };

  const handleDelete = async () => {
    if (!deleteItem) return;
    setIsDeleting(true);
    try {
      await financeApi.deleteExternalCost(storeId, deleteItem.id);
      success("Deleted", "External cost removed.");
      setDeleteItem(null);
      onRefresh();
    } catch (err) {
      error("Delete failed", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <div className="rounded-xl border border-zinc-200 bg-white shadow-soft-sm overflow-hidden">
        <div className="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
          <span className="text-sm font-medium text-zinc-700">{total} external costs</span>
          <Button variant="brand" size="sm" onClick={openCreate}>
            <Plus size={13} className="mr-1.5" />
            Add Cost
          </Button>
        </div>

        {isLoading ? (
          <div className="divide-y divide-zinc-100">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-4 py-3">
                <div className="shimmer h-4 w-24 rounded" />
                <div className="shimmer h-4 w-16 rounded" />
                <div className="shimmer h-4 w-24 rounded" />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-12 text-center">
            <Plus size={28} className="text-zinc-300" />
            <p className="text-sm text-zinc-500">No external costs recorded.</p>
            <p className="text-xs text-zinc-400">
              Add costs like ads, salaries, or rent to improve profit accuracy.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-100 bg-zinc-50">
                  {["Date", "Period", "Type", "Amount", "Allocation", "Note", ""].map((col) => (
                    <th
                      key={col}
                      className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-zinc-400"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-50">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-zinc-50/50 transition-colors">
                    <td className="whitespace-nowrap px-3 py-2.5 text-zinc-700">
                      {formatDate(item.costDate)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-zinc-500 text-xs">
                      {formatDate(item.periodFrom)} — {formatDate(item.periodTo)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5">
                      <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600">
                        {item.costType}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 font-medium text-zinc-800">
                      {formatMoney(item.amount, item.currency)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-xs text-zinc-500">
                      {item.allocationMethod}
                    </td>
                    <td className="max-w-[140px] px-3 py-2.5">
                      <span className="block truncate text-xs text-zinc-500">
                        {item.note ?? "—"}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5">
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" onClick={() => openEdit(item)}>
                          <Edit2 size={13} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleteItem(item)}
                          className="text-red-500 hover:bg-red-50 hover:text-red-600"
                        >
                          <Trash2 size={13} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-zinc-100 px-4 py-3">
            <span className="text-xs text-zinc-400">
              Page {page} of {totalPages}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPageChange(page - 1)}
                disabled={page <= 1}
              >
                <ChevronLeft size={14} />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPageChange(page + 1)}
                disabled={page >= totalPages}
              >
                <ChevronRight size={14} />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Create / Edit Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title={editItem ? `Edit Cost #${editItem.id}` : "Add External Cost"}
        className="max-w-lg"
      >
        <form onSubmit={handleSubmit(onSave)} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Cost Date"
              type="date"
              error={errors.cost_date?.message}
              {...register("cost_date", { required: "Required" })}
            />
            <div>
              <label className="mb-1.5 block text-sm font-medium text-zinc-700">Type</label>
              <select
                {...register("cost_type")}
                className="flex h-10 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm focus:border-brand focus:outline-none"
              >
                {COST_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <Input
              label="Period From"
              type="date"
              error={errors.period_from?.message}
              {...register("period_from", { required: "Required" })}
            />
            <Input
              label="Period To"
              type="date"
              error={errors.period_to?.message}
              {...register("period_to", { required: "Required" })}
            />
            <Input
              label="Amount"
              type="number"
              step="0.01"
              min="0"
              error={errors.amount?.message}
              {...register("amount", {
                required: "Required",
                min: { value: 0, message: "Must be >= 0" },
              })}
            />
            <div>
              <label className="mb-1.5 block text-sm font-medium text-zinc-700">Currency</label>
              <select
                {...register("currency")}
                className="flex h-10 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm focus:border-brand focus:outline-none"
              >
                <option value="RUB">RUB</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="mb-1.5 block text-sm font-medium text-zinc-700">
                Allocation Method
              </label>
              <select
                {...register("allocation_method")}
                className="flex h-10 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm focus:border-brand focus:outline-none"
              >
                {ALLOCATION_METHODS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <Input
            label="Note"
            placeholder="Optional note"
            {...register("note")}
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="brand" isLoading={isSubmitting}>
              {editItem ? "Update" : "Add"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete confirmation */}
      <ConfirmDialog
        isOpen={Boolean(deleteItem)}
        onCancel={() => setDeleteItem(null)}
        onConfirm={handleDelete}
        title="Delete External Cost"
        description={`Remove this ${deleteItem?.costType} cost of ${formatMoney(deleteItem?.amount ?? "0", deleteItem?.currency)}? This cannot be undone.`}
        confirmLabel="Delete"
        isLoading={isDeleting}
      />
    </>
  );
}
