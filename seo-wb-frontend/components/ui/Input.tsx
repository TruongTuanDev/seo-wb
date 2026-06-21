import React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  label?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, label, ...props }, ref) => {
    return (
      <div className="w-full flex flex-col gap-1.5">
        {label && (
          <label className="text-sm font-medium text-zinc-700">
            {label}
            {props.required && <span className="text-brand ml-1">*</span>}
          </label>
        )}
        <input
          ref={ref}
          className={cn(
            "flex h-10 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-soft-sm ring-offset-white transition-[color,background-color,border-color,box-shadow] duration-200 file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-zinc-400 hover:border-zinc-400 focus-visible:border-brand focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand/15 disabled:cursor-not-allowed disabled:bg-zinc-100 disabled:opacity-60",
            error && "border-rose-500 hover:border-rose-500 focus-visible:border-rose-500 focus-visible:ring-rose-500/15",
            className
          )}
          {...props}
        />
        {error && <span className="text-xs text-rose-500">{error}</span>}
      </div>
    );
  }
);
Input.displayName = "Input";
