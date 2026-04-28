"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, User as UserIcon, ChevronDown } from "lucide-react";
import { useState } from "react";
import { authApi } from "@/lib/api";
import { clearAuth, getUser } from "@/lib/auth";
import toast from "react-hot-toast";

export default function Navbar() {
  const router = useRouter();
  const user = getUser();
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore
    }
    clearAuth();
    toast.success("Signed out");
    router.push("/login");
  };

  return (
    <nav className="h-14 border-b border-axon-border bg-axon-bg/95 backdrop-blur-sm flex items-center px-6 gap-6">
      <Link href="/dashboard" className="font-mono text-lg font-semibold text-white">
        AX<span className="text-axon-cyan">ON</span>
      </Link>

      <div className="flex-1" />

      <div className="relative">
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-axon-border hover:border-axon-muted transition-colors text-sm"
        >
          <div className="w-6 h-6 rounded-full bg-axon-surface border border-axon-border flex items-center justify-center">
            <UserIcon size={12} className="text-axon-cyan" />
          </div>
          <span className="text-axon-text max-w-[120px] truncate">
            {user?.name || user?.email || "Account"}
          </span>
          <ChevronDown size={12} className="text-axon-muted" />
        </button>

        {menuOpen && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
            <div className="absolute right-0 top-full mt-1 w-44 rounded-xl border border-axon-border bg-axon-surface shadow-xl z-20 overflow-hidden">
              <div className="px-3 py-2 border-b border-axon-border">
                <p className="text-xs text-axon-muted truncate">{user?.email}</p>
              </div>
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-axon-muted hover:text-red-400 hover:bg-axon-bg transition-colors"
              >
                <LogOut size={14} />
                Sign out
              </button>
            </div>
          </>
        )}
      </div>
    </nav>
  );
}
