"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const STORAGE_KEY = "wb_selected_store_id";

export interface StoreItem {
  id: number;
  name: string;
}

interface StoreContextValue {
  stores: StoreItem[];
  currentStoreId: number | null;
  isLoading: boolean;
  setCurrentStoreId: (id: number) => void;
  loadStores: () => void;
  addStore: (store: StoreItem) => void;
  updateStore: (store: StoreItem) => void;
  /** Removes the store, updates currentStoreId, returns the new currentStoreId (or null) */
  removeStore: (storeId: number) => number | null;
}

const StoreContext = createContext<StoreContextValue>({
  stores: [],
  currentStoreId: null,
  isLoading: true,
  setCurrentStoreId: () => {},
  loadStores: () => {},
  addStore: () => {},
  updateStore: () => {},
  removeStore: () => null,
});

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [stores, setStores] = useState<StoreItem[]>([]);
  const [currentStoreId, setCurrentStoreIdState] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const setCurrentStoreId = (id: number) => {
    setCurrentStoreIdState(id);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, String(id));
    }
  };

  const loadStores = useCallback(() => {
    setIsLoading(true);
    api
      .get("/stores", { redirectOnUnauthorized: false })
      .then((data) => {
        const list: StoreItem[] = Array.isArray(data) ? data : (data.items ?? []);
        setStores(list);
        const saved = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
        const savedId = saved ? Number(saved) : null;
        const found = savedId ? list.find((s) => s.id === savedId) : null;
        if (found) {
          setCurrentStoreIdState(savedId);
        } else if (list.length > 0) {
          setCurrentStoreIdState(list[0].id);
          if (typeof window !== "undefined") {
            localStorage.setItem(STORAGE_KEY, String(list[0].id));
          }
        }
      })
      .catch(() => setStores([]))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    queueMicrotask(() => loadStores());
  }, [loadStores]);

  const addStore = (store: StoreItem) => {
    setStores((prev) => [...prev, store]);
    setCurrentStoreId(store.id);
  };

  const updateStore = (store: StoreItem) => {
    setStores((prev) => prev.map((s) => (s.id === store.id ? store : s)));
  };

  const removeStore = (storeId: number): number | null => {
    const next = stores.filter((s) => s.id !== storeId);
    setStores(next);
    if (currentStoreId === storeId) {
      const fallback = next[0]?.id ?? null;
      if (fallback) {
        setCurrentStoreId(fallback);
      } else {
        setCurrentStoreIdState(null);
        if (typeof window !== "undefined") localStorage.removeItem(STORAGE_KEY);
      }
      return fallback;
    }
    return currentStoreId;
  };

  return (
    <StoreContext.Provider
      value={{ stores, currentStoreId, isLoading, setCurrentStoreId, loadStores, addStore, updateStore, removeStore }}
    >
      {children}
    </StoreContext.Provider>
  );
}

export function useStore() {
  return useContext(StoreContext);
}
