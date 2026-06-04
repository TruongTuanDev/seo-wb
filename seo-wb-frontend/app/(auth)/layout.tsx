import React from "react";
import { PageTransition } from "@/components/ui/PageTransition";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 p-4">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-100 via-zinc-50 to-zinc-50"></div>
      <div className="relative z-10 w-full max-w-md overflow-hidden rounded-xl border border-zinc-200 bg-white p-6 shadow-soft-xl sm:p-8">
        {/* Decorative top bar */}
        <div className="absolute left-0 right-0 top-0 h-1 bg-gradient-to-r from-indigo-300 via-brand to-violet-400"></div>
        <PageTransition>{children}</PageTransition>
      </div>
    </div>
  );
}
