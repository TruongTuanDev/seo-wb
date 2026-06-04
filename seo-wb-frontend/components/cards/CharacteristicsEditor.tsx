"use client";

import React, { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/Input";
import { Spinner } from "@/components/ui/Spinner";

export interface Characteristic {
  id: number;
  name: string;
  value: string | string[]; // Can be string or array of strings depending on multiple
}

interface WBSchemaCharc {
  charcID: number;
  name: string;
  required: boolean;
  unitName: string;
  maxCount: number;
  popular: boolean;
  charcType: number;
}

interface CharacteristicsEditorProps {
  storeId: number;
  subjectId: number;
  characteristics: Characteristic[];
  onChange: (charcs: Characteristic[]) => void;
  readOnly?: boolean;
}

export function CharacteristicsEditor({
  storeId,
  subjectId,
  characteristics,
  onChange,
  readOnly = false,
}: CharacteristicsEditorProps) {
  const [schema, setSchema] = useState<WBSchemaCharc[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!storeId || !subjectId) return;

    const fetchSchema = async () => {
      setLoading(true);
      try {
        const data = await api.get(`/wb/subjects/${subjectId}/charcs?store_id=${storeId}`);
        setSchema(data?.data || data || []);
      } catch (err) {
        console.error("Failed to fetch charc schema", err);
      } finally {
        setLoading(false);
      }
    };

    fetchSchema();
  }, [storeId, subjectId]);

  const updateCharcValue = (id: number, name: string, val: string) => {
    const existing = characteristics.find((c) => c.id === id);
    let newValue: Characteristic[];
    
    // Check if the schema allows multiple via maxCount. If maxCount > 1, maybe comma-separated for simple edit.
    // For now, let's keep it simple: string. We can parse commas to arrays later if needed.
    
    if (existing) {
      newValue = characteristics.map((c) => 
         c.id === id ? { ...c, value: val } : c
      );
    } else {
      newValue = [...characteristics, { id, name, value: val }];
    }
    
    // Filter out empties if we removed text
    if (val.trim() === "") {
        newValue = newValue.filter(c => c.id !== id);
    }
    
    onChange(newValue);
  };

  const splitValues = (value: string) =>
    value
      .split(/[,;]+/)
      .map((item) => item.trim())
      .filter(Boolean);

  const validateCharc = (charc: WBSchemaCharc, value: string) => {
    const trimmed = value.trim();
    if (charc.required && !trimmed) {
      return "Required by Wildberries";
    }
    if (charc.maxCount > 0 && splitValues(trimmed).length > charc.maxCount) {
      return `Maximum ${charc.maxCount} value(s)`;
    }
    if (charc.charcType === 4 && trimmed && Number.isNaN(Number(trimmed.replace(",", ".")))) {
      return "Expected a numeric value";
    }
    return "";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-zinc-50 p-8">
        <Spinner />
      </div>
    );
  }

  // Group schema: Required, Popular, Optional
  const required = schema.filter((c) => c.required);
  const popular = schema.filter((c) => !c.required && c.popular);
  const optional = schema.filter((c) => !c.required && !c.popular);

  const renderSection = (title: string, list: WBSchemaCharc[]) => {
    if (list.length === 0) return null;
    return (
      <div className="mb-6 space-y-3">
        <h3 className="border-b border-zinc-200 pb-2 text-sm font-medium text-zinc-700">{title}</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {list.map((c) => {
             const currentValue = characteristics.find(val => val.id === c.charcID)?.value;
             const displayValue = Array.isArray(currentValue) ? currentValue.join(", ") : (currentValue || "");
             const fieldError = validateCharc(c, displayValue);
             
             return (
              <div key={c.charcID} className="flex flex-col gap-1">
                <label className="text-xs font-medium text-zinc-400 flex justify-between">
                  <span className="text-zinc-600">{c.name} {c.required && <span className="text-brand">*</span>}</span>
                  {c.unitName && <span className="text-zinc-400">[{c.unitName}]</span>}
                </label>
                <Input
                  value={displayValue}
                  onChange={(e) => updateCharcValue(c.charcID, c.name, e.target.value)}
                  readOnly={readOnly}
                  className="h-9 text-sm"
                  placeholder={c.maxCount > 1 ? `Up to ${c.maxCount} values (comma separated)` : ""}
                  error={fieldError}
                />
              </div>
             );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-2">
      {renderSection("Required Characteristics", required)}
      {renderSection("Popular Characteristics", popular)}
      <details className="group">
        <summary className="mb-4 flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-brand transition-colors duration-150 hover:text-brand-hover">
           <Plus size={16} className="group-open:rotate-45 transition-transform" />
           Show Optional Characteristics
        </summary>
        <div className="pt-2">
          {renderSection("Optional", optional)}
        </div>
      </details>
    </div>
  );
}
