"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export const dynamic = "force-dynamic";

export default function ExternalCostsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/finance/settings");
  }, [router]);

  return null;
}
