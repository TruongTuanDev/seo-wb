import { Suspense } from "react";
import { DashboardClientLayout } from "@/app/(dashboard)/DashboardClientLayout";
import { StoreProvider } from "@/contexts/StoreContext";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <StoreProvider>
      <Suspense fallback={<div className="min-h-screen bg-zinc-50" />}>
        <DashboardClientLayout>{children}</DashboardClientLayout>
      </Suspense>
    </StoreProvider>
  );
}
