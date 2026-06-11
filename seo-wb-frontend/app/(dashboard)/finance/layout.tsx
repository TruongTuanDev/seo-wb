import { redirect } from "next/navigation";
import { FINANCE_ENABLED } from "@/lib/features";

export default function FinanceLayout({ children }: { children: React.ReactNode }) {
  if (!FINANCE_ENABLED) {
    redirect("/");
  }

  return children;
}
