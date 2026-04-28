import { Suspense } from "react";
import LoginClient from "@/components/LoginClient";

function Skeleton() {
  return (
    <div className="min-h-screen bg-axon-bg flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="h-8 w-20 bg-axon-surface rounded mx-auto mb-8 animate-pulse" />
        <div className="p-8 rounded-2xl border border-axon-border bg-axon-surface space-y-4">
          <div className="h-10 rounded-lg bg-axon-bg animate-pulse" />
          <div className="h-px bg-axon-border" />
          <div className="h-9 rounded-lg bg-axon-bg animate-pulse" />
          <div className="h-9 rounded-lg bg-axon-bg animate-pulse" />
          <div className="h-10 rounded-lg bg-axon-bg animate-pulse" />
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<Skeleton />}>
      <LoginClient />
    </Suspense>
  );
}
