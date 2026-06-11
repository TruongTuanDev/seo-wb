"use client";

import React, { createContext, useContext, useState, ReactNode, useCallback } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export type ToastType = "success" | "error" | "info" | "warning";

export interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
}

interface ToastContextType {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((toast: Omit<Toast, "id">) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { ...toast, id }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000); // auto-remove after 5s
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const success = useCallback((title: string, message?: string) => {
    addToast({ type: "success", title, message });
  }, [addToast]);

  const error = useCallback((title: string, message?: string) => {
    addToast({ type: "error", title, message });
  }, [addToast]);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast, success, error }}>
      {children}
      <div className="fixed inset-x-4 bottom-4 z-50 flex flex-col gap-2 sm:left-auto sm:right-4 sm:w-[min(28rem,calc(100vw-2rem))]">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cn(
              "flex w-full min-w-0 items-start justify-between rounded bg-zinc-900 p-4 shadow-lg border border-zinc-800 text-white animate-in slide-in-from-right-full fade-in duration-300",
              toast.type === "success" && "border-green-600/50",
              toast.type === "error" && "border-red-600/50",
            )}
          >
            <div className="flex min-w-0 flex-col gap-1">
              <span className={cn(
                  "font-semibold text-sm",
                  toast.type === 'success' && "text-green-400",
                  toast.type === 'error' && "text-red-400"
              )}>
                {toast.title}
              </span>
              {toast.message && (
                <span className="max-h-48 overflow-y-auto whitespace-pre-wrap break-words text-sm text-zinc-400">
                  {toast.message}
                </span>
              )}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="ml-4 text-zinc-400 hover:text-white shrink-0"
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
