"use client";

import React, { useEffect } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export function Modal({ isOpen, onClose, title, description, children, className }: ModalProps) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-zinc-900/40 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onClose}
      />
      
      {/* Dialog */}
      <div className={cn(
        "relative z-10 max-h-[calc(100vh-2rem)] w-full max-w-lg overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-soft-xl animate-in fade-in zoom-in-95 duration-300",
        className
      )}>
        <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-950">{title}</h2>
            {description && <p className="text-sm text-zinc-500 mt-1">{description}</p>}
          </div>
          <button 
            onClick={onClose}
            className="rounded-full p-1.5 text-zinc-500 transition-all duration-150 hover:bg-zinc-100 hover:text-zinc-950 active:scale-95 focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2"
          >
            <X size={20} />
          </button>
        </div>
        
        <div className="max-h-[calc(100vh-8rem)] overflow-y-auto p-6">
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
}
