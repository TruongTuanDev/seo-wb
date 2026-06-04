"use client";

import React, { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";
import { Spinner } from "@/components/ui/Spinner";
import { Input } from "@/components/ui/Input";

interface Category {
  id: number;
  name: string;
}

interface Subject {
  id: number;
  name: string;
}

interface CategorySelectorProps {
  storeId: number;
  selectedSubjectId?: number;
  selectedSubjectName?: string;
  onSubjectSelected: (subjectId: number, name: string) => void;
}

export function CategorySelector({ storeId, selectedSubjectId, selectedSubjectName, onSubjectSelected }: CategorySelectorProps) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  
  const [selectedCategory, setSelectedCategory] = useState<number | "">("");
  const [selectedSubject, setSelectedSubject] = useState<number | "">(selectedSubjectId || "");
  const [subjectQuery, setSubjectQuery] = useState(selectedSubjectName || "");
  
  const [loadingCats, setLoadingCats] = useState(false);
  const [loadingSubjects, setLoadingSubjects] = useState(false);
  const { error } = useToast();
  const onSubjectSelectedRef = useRef(onSubjectSelected);

  useEffect(() => {
    onSubjectSelectedRef.current = onSubjectSelected;
  }, [onSubjectSelected]);

  const normalizeCategory = (item: Record<string, unknown>): Category => ({
    id: Number(item.id ?? item.parentID ?? item.subjectID ?? 0),
    name: String(item.name ?? item.parentName ?? item.subjectName ?? ""),
  });

  const normalizeSubject = (item: Record<string, unknown>): Subject => ({
    id: Number(item.id ?? item.subjectID ?? 0),
    name: String(item.name ?? item.subjectName ?? ""),
  });

  useEffect(() => {
    queueMicrotask(() => {
      if (selectedSubjectId) {
        setSelectedSubject(selectedSubjectId);
      }
      if (selectedSubjectName) {
        setSubjectQuery(selectedSubjectName);
      }
    });
  }, [selectedSubjectId, selectedSubjectName]);

  useEffect(() => {
    if (!storeId) return;
    
    const fetchCategories = async () => {
      setLoadingCats(true);
      try {
        const data = await api.get(`/wb/parent-categories?store_id=${storeId}`);
        const normalized = (data?.data || data || [])
          .map(normalizeCategory)
          .filter((item: Category) => item.id && item.name);
        setCategories(normalized);
        // Defaults to category 1 (clothes) based on PRD if available
        const defaultCat = normalized.find((c: Category) => c.id === 1);
        if (defaultCat) {
          setSelectedCategory(1);
        }
      } catch (err: unknown) {
        error("Failed to fetch categories", getErrorMessage(err));
      } finally {
        setLoadingCats(false);
      }
    };
    
    fetchCategories();
  }, [storeId, error]);

  useEffect(() => {
    if (!storeId || !selectedCategory) return;

    const fetchSubjects = async () => {
      setLoadingSubjects(true);
      try {
        const q = subjectQuery ? `&q=${encodeURIComponent(subjectQuery)}` : "";
        const data = await api.get(`/wb/subjects?store_id=${storeId}&parent_id=${selectedCategory}${q}`);
        const normalized = (data?.data || data || [])
          .map(normalizeSubject)
          .filter((item: Subject) => item.id && item.name);
        setSubjects(normalized);
        const exact = normalized.find(
          (item: Subject) => item.name.toLocaleLowerCase("ru") === subjectQuery.trim().toLocaleLowerCase("ru")
        );
        const autoSelected = exact || (subjectQuery.trim() && normalized.length === 1 ? normalized[0] : null);
        if (autoSelected) {
          setSelectedSubject(autoSelected.id);
          onSubjectSelectedRef.current(autoSelected.id, autoSelected.name);
        } else if (selectedSubjectId) {
          const selected = normalized.find((item: Subject) => item.id === selectedSubjectId);
          if (selected) {
            setSelectedSubject(selected.id);
            onSubjectSelectedRef.current(selected.id, selected.name);
          }
        }
      } catch (err: unknown) {
         error("Failed to fetch subjects", getErrorMessage(err));
      } finally {
        setLoadingSubjects(false);
      }
    };

    // Debounce query
    const timer = setTimeout(() => {
        fetchSubjects();
    }, 500);

    return () => clearTimeout(timer);
  }, [storeId, selectedCategory, subjectQuery, selectedSubjectId, error]);

  const handleSubjectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = parseInt(e.target.value);
    setSelectedSubject(val);
    const subjName = subjects.find(s => s.id === val)?.name || "";
    if (val) onSubjectSelected(val, subjName);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="flex flex-col gap-1.5">
         <label className="text-sm font-medium text-zinc-700">
            Parent Category <span className="text-brand ml-1">*</span>
         </label>
         <div className="relative">
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value ? parseInt(e.target.value) : "")}
              disabled={loadingCats}
              className="flex h-10 w-full appearance-none rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-soft-sm transition-colors duration-150 focus-visible:border-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-100 disabled:opacity-50"
            >
              <option value="" disabled>Select category</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            {loadingCats && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                <Spinner size="sm" />
              </div>
            )}
         </div>
      </div>

      <div className="flex flex-col gap-1.5">
         <label className="text-sm font-medium text-zinc-700">
            Subject (Item Type) <span className="text-brand ml-1">*</span>
         </label>
         <div className="flex flex-col gap-2">
           <Input 
             placeholder="Search subject (e.g. Брюки)" 
             value={subjectQuery}
             onChange={(e) => setSubjectQuery(e.target.value)}
           />
           <div className="relative">
              <select
                value={selectedSubject}
                onChange={handleSubjectChange}
                disabled={!selectedCategory || loadingSubjects}
                className="flex h-10 w-full appearance-none rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-soft-sm transition-colors duration-150 focus-visible:border-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-100 disabled:opacity-50"
              >
                <option value="" disabled>Select subject</option>
                {selectedSubjectId && selectedSubjectName && !subjects.some((s) => s.id === selectedSubjectId) && (
                  <option value={selectedSubjectId}>{selectedSubjectName}</option>
                )}
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
              {loadingSubjects && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <Spinner size="sm" />
                </div>
              )}
           </div>
         </div>
      </div>
    </div>
  );
}

function getErrorMessage(err: unknown) {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "Unknown error";
}
