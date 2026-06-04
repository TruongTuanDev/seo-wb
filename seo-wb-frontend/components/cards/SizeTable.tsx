"use client";

import React from "react";
import { Plus, Trash } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export interface SizeRow {
  techSize: string;
  wbSize: string;
  sku: string;
}

interface SizeTableProps {
  sizes: SizeRow[];
  onChange: (sizes: SizeRow[]) => void;
  readOnly?: boolean;
}

export function SizeTable({ sizes, onChange, readOnly = false }: SizeTableProps) {
  const addRow = () => {
    onChange([...sizes, { techSize: "", wbSize: "", sku: "" }]);
  };

  const removeRow = (index: number) => {
    onChange(sizes.filter((_, i) => i !== index));
  };

  const updateRow = (index: number, field: keyof SizeRow, value: string) => {
    const newSizes = [...sizes];
    newSizes[index] = { ...newSizes[index], [field]: value };
    onChange(newSizes);
  };

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-soft-sm">
        <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-left text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50/80 text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-4 py-3 font-medium">Tech Size (Supplier)</th>
              <th className="px-4 py-3 font-medium">WB Size (Customer)</th>
              <th className="px-4 py-3 font-medium">Barcode / SKU</th>
              {!readOnly && <th className="px-4 py-3 font-medium text-right w-16">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {sizes.map((row, idx) => (
              <tr key={idx} className="border-b border-zinc-200/80 transition-colors duration-150 last:border-0 hover:bg-zinc-50">
                <td className="p-2">
                  <Input 
                    value={row.techSize} 
                    onChange={(e) => updateRow(idx, "techSize", e.target.value)}
                    placeholder="e.g. S, 42"
                    readOnly={readOnly}
                    className="h-8"
                  />
                </td>
                <td className="p-2">
                  <Input 
                    value={row.wbSize} 
                    onChange={(e) => updateRow(idx, "wbSize", e.target.value)}
                    placeholder="e.g. 42-44"
                    readOnly={readOnly}
                    className="h-8"
                  />
                </td>
                <td className="p-2">
                  <Input 
                    value={row.sku} 
                    onChange={(e) => updateRow(idx, "sku", e.target.value)}
                    placeholder="Auto-generated if empty"
                    readOnly={readOnly}
                    className="h-8"
                  />
                </td>
                {!readOnly && (
                  <td className="p-2 text-right">
                    <button 
                      type="button"
                      onClick={() => removeRow(idx)}
                      className="rounded p-1.5 text-zinc-500 transition-colors duration-150 hover:bg-rose-50 hover:text-rose-500 disabled:opacity-30"
                      disabled={sizes.length <= 1}
                    >
                      <Trash size={16} />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
      {!readOnly && (
        <Button type="button" variant="outline" size="sm" onClick={addRow}>
          <Plus size={16} className="mr-2" /> Add Size Option
        </Button>
      )}
    </div>
  );
}
