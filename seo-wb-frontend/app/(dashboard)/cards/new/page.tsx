import { Suspense } from "react";
import { CreateCardClient } from "@/app/(dashboard)/cards/new/CreateCardClient";
import { Spinner } from "@/components/ui/Spinner";

export const dynamic = "force-dynamic";

export default function CreateCardPage() {
  return (
    <Suspense fallback={<div className="flex justify-center p-10"><Spinner /></div>}>
      <CreateCardClient />
    </Suspense>
  );
}
