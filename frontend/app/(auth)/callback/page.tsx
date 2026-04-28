import { Suspense } from "react";
import CallbackClient from "@/components/CallbackClient";
import { Loader2 } from "lucide-react";

function Spinner() {
  return (
    <div className="min-h-screen bg-axon-bg flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <Loader2 size={24} className="animate-spin text-axon-cyan" />
        <p className="text-sm text-axon-muted">Signing you in…</p>
      </div>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <CallbackClient />
    </Suspense>
  );
}
