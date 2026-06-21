import React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "solid" | "outline" | "ghost" | "danger" | "brand";
  size?: "sm" | "md" | "lg" | "icon";
  isLoading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "solid", size = "md", isLoading, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          "relative inline-flex min-w-0 items-center justify-center rounded-lg font-medium whitespace-nowrap transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/70 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98] active:translate-y-0",
          "focus-visible:ring-offset-2 focus-visible:ring-offset-white",
          {
            // Variants
            "bg-brand text-white shadow-soft-sm hover:bg-brand-hover hover:-translate-y-px hover:shadow-[var(--shadow-brand)]": variant === "primary" || variant === "brand",
            "bg-zinc-100 text-zinc-900 shadow-soft-sm hover:bg-zinc-200 hover:shadow-soft-md": variant === "secondary" || variant === "solid",
            "border border-zinc-300 bg-white text-zinc-800 shadow-soft-sm hover:border-zinc-400 hover:bg-zinc-50 hover:shadow-soft-md": variant === "outline",
            "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950": variant === "ghost",
            "bg-rose-600 text-white shadow-soft-sm hover:bg-rose-700 hover:-translate-y-px hover:shadow-[0_6px_16px_-4px_rgb(225_29_72_/_0.35)]": variant === "danger",

            // Sizes
            "h-9 px-3.5 text-xs": size === "sm",
            "h-10 px-4 py-2 text-sm": size === "md",
            "h-11 rounded-lg px-8": size === "lg",
            "h-10 w-10 p-2": size === "icon",
          },
          className
        )}
        {...props}
      >
        <span className={cn("inline-flex min-w-0 items-center justify-center gap-2 truncate", isLoading && "opacity-0")}>
          {children}
        </span>
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <svg
              className="h-5 w-5 animate-spin"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              ></circle>
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
          </div>
        )}
      </button>
    );
  }
);
Button.displayName = "Button";
