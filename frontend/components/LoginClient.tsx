"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import toast from "react-hot-toast";
import { authApi } from "@/lib/api";
import { saveAuth, User } from "@/lib/auth";
import GoogleSignInButton from "@/components/GoogleSignInButton";

export default function LoginClient() {
  const router = useRouter();
  const params = useSearchParams();
  const [form, setForm] = useState({ email: "", password: "" });
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const err = params?.get("error");
    if (err) {
      const messages: Record<string, string> = {
        google_denied: "Google sign-in was cancelled.",
        google_token_failed: "Google sign-in failed. Please try again.",
        google_userinfo_failed: "Could not fetch your Google profile.",
      };
      toast.error(messages[err] || "Sign-in failed.");
    }
  }, [params]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.email || !form.password) { toast.error("Fill in all fields"); return; }
    setLoading(true);
    try {
      const { data } = await authApi.login(form.email, form.password);
      saveAuth(data.access_token, data.user as User);
      toast.success("Welcome back");
      router.push("/dashboard");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Login failed";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-axon-bg flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <Link href="/" className="inline-block font-mono text-2xl font-semibold text-axon-text">
            AX<span className="text-axon-cyan">ON</span>
          </Link>
          <p className="mt-2 text-sm text-axon-muted">Sign in to your account</p>
        </div>

        <div className="p-8 rounded-2xl border border-axon-border bg-axon-surface space-y-5">
          <GoogleSignInButton label="Sign in with Google" disabled={loading} />

          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-axon-border" />
            <span className="text-xs text-axon-muted">or</span>
            <div className="flex-1 h-px bg-axon-border" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-axon-muted mb-1.5 font-mono uppercase tracking-wide">Email</label>
              <input type="email" autoComplete="email"
                className="w-full bg-axon-bg border border-axon-border rounded-lg px-4 py-2.5 text-sm text-axon-text placeholder-axon-muted transition-colors"
                placeholder="you@example.com"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="block text-xs text-axon-muted mb-1.5 font-mono uppercase tracking-wide">Password</label>
              <div className="relative">
                <input type={showPw ? "text" : "password"} autoComplete="current-password"
                  className="w-full bg-axon-bg border border-axon-border rounded-lg px-4 py-2.5 text-sm text-axon-text placeholder-axon-muted transition-colors pr-10"
                  placeholder="••••••••"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  required
                />
                <button type="button" onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-axon-muted hover:text-axon-text">
                  {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>
            <button type="submit" disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-axon-cyan text-axon-bg font-semibold text-sm hover:bg-white transition-colors disabled:opacity-60">
              {loading && <Loader2 size={14} className="animate-spin" />}
              {loading ? "Signing in…" : "Sign in with email"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-axon-muted mt-5">
          No account?{" "}
          <Link href="/signup" className="text-axon-cyan hover:underline">Create one</Link>
        </p>
      </div>
    </div>
  );
}
