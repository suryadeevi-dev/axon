"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import toast from "react-hot-toast";
import { authApi } from "@/lib/api";
import { saveAuth, User } from "@/lib/auth";

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "" });
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.password !== form.confirm) {
      toast.error("Passwords don't match");
      return;
    }
    if (form.password.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      const { data } = await authApi.signup(form.email, form.password, form.name);
      saveAuth(data.access_token, data.user as User);
      toast.success("Account created — welcome to AXON");
      router.push("/dashboard");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Signup failed";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const field = (label: string, key: keyof typeof form, type = "text", ph = "") => (
    <div>
      <label className="block text-xs text-axon-muted mb-1.5 font-mono uppercase tracking-wide">
        {label}
      </label>
      <input
        type={type === "password" && showPw ? "text" : type}
        autoComplete={key === "email" ? "email" : key === "name" ? "name" : "new-password"}
        className="w-full bg-axon-bg border border-axon-border rounded-lg px-4 py-2.5 text-sm text-white placeholder-axon-muted transition-colors"
        placeholder={ph}
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        required
      />
    </div>
  );

  return (
    <div className="min-h-screen bg-axon-bg flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <Link href="/" className="inline-block font-mono text-2xl font-semibold text-white">
            AX<span className="text-axon-cyan">ON</span>
          </Link>
          <p className="mt-2 text-sm text-axon-muted">Create your account</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="p-8 rounded-2xl border border-axon-border bg-axon-surface space-y-5"
        >
          {field("Full name", "name", "text", "Ada Lovelace")}
          {field("Email", "email", "email", "you@example.com")}

          <div>
            <label className="block text-xs text-axon-muted mb-1.5 font-mono uppercase tracking-wide">
              Password
            </label>
            <div className="relative">
              <input
                type={showPw ? "text" : "password"}
                autoComplete="new-password"
                className="w-full bg-axon-bg border border-axon-border rounded-lg px-4 py-2.5 text-sm text-white placeholder-axon-muted transition-colors pr-10"
                placeholder="min 8 characters"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-axon-muted hover:text-white"
                onClick={() => setShowPw(!showPw)}
              >
                {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>

          {field("Confirm password", "confirm", "password", "repeat password")}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-axon-cyan text-axon-bg font-semibold text-sm hover:bg-white transition-colors disabled:opacity-60"
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            {loading ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="text-center text-xs text-axon-muted mt-5">
          Already have an account?{" "}
          <Link href="/login" className="text-axon-cyan hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
