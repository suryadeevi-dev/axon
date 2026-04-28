"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, AlertCircle } from "lucide-react";
import { saveAuth, User } from "@/lib/auth";

const ERROR_MESSAGES: Record<string, string> = {
  google_denied: "You cancelled the Google sign-in.",
  google_token_failed: "Could not exchange Google token. Try again.",
  google_userinfo_failed: "Could not fetch your Google profile. Try again.",
  google_no_email: "Google account has no email address.",
};

export default function CallbackPage() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = params?.get("token");
    const userB64 = params?.get("user");
    const errCode = params?.get("error");

    if (errCode) {
      setError(ERROR_MESSAGES[errCode] || "Sign-in failed. Please try again.");
      return;
    }

    if (!token || !userB64) {
      setError("Missing session data. Please try signing in again.");
      return;
    }

    try {
      const user = JSON.parse(atob(userB64)) as User;
      saveAuth(token, user);
      router.replace("/dashboard");
    } catch {
      setError("Could not parse session. Please try signing in again.");
    }
  }, [params]);

  if (error) {
    return (
      <div className="min-h-screen bg-axon-bg flex items-center justify-center px-6">
        <div className="w-full max-w-sm text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-red-500/10 border border-red-500/30 mb-4">
            <AlertCircle size={20} className="text-red-400" />
          </div>
          <p className="text-sm font-medium text-white mb-1">Sign-in failed</p>
          <p className="text-xs text-axon-muted mb-6">{error}</p>
          <button
            onClick={() => router.push("/login")}
            className="px-5 py-2 rounded-lg bg-axon-cyan text-axon-bg text-sm font-semibold hover:bg-white transition-colors"
          >
            Back to login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-axon-bg flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <Loader2 size={24} className="animate-spin text-axon-cyan" />
        <p className="text-sm text-axon-muted">Signing you in…</p>
      </div>
    </div>
  );
}
