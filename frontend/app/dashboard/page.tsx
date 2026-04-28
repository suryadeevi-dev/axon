"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Loader2, Cpu, X } from "lucide-react";
import toast from "react-hot-toast";
import Navbar from "@/components/Navbar";
import AgentCard from "@/components/AgentCard";
import { agentsApi } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

interface Agent {
  id: string;
  name: string;
  description?: string;
  status: "running" | "stopped" | "starting" | "error";
  created_at: string;
  last_active?: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    loadAgents();
  }, []);

  const loadAgents = async () => {
    try {
      const { data } = await agentsApi.list();
      setAgents(data.agents || []);
    } catch {
      toast.error("Failed to load agents");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const { data } = await agentsApi.create(newName.trim(), newDesc.trim());
      setAgents((prev) => [data.agent, ...prev]);
      setShowCreate(false);
      setNewName("");
      setNewDesc("");
      toast.success(`Agent "${data.agent.name}" provisioned`);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Failed to create agent";
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  };

  const handleStart = async (id: string) => {
    setActionLoading(id);
    try {
      await agentsApi.start(id);
      setAgents((prev) =>
        prev.map((a) => (a.id === id ? { ...a, status: "starting" } : a))
      );
      toast.success("Agent starting…");
      setTimeout(() => {
        setAgents((prev) =>
          prev.map((a) => (a.id === id ? { ...a, status: "running" } : a))
        );
      }, 3000);
    } catch {
      toast.error("Failed to start agent");
    } finally {
      setActionLoading(null);
    }
  };

  const handleStop = async (id: string) => {
    setActionLoading(id);
    try {
      await agentsApi.stop(id);
      setAgents((prev) =>
        prev.map((a) => (a.id === id ? { ...a, status: "stopped" } : a))
      );
      toast.success("Agent stopped");
    } catch {
      toast.error("Failed to stop agent");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this agent? This is irreversible.")) return;
    setActionLoading(id);
    try {
      await agentsApi.delete(id);
      setAgents((prev) => prev.filter((a) => a.id !== id));
      toast.success("Agent deleted");
    } catch {
      toast.error("Failed to delete agent");
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="min-h-screen bg-axon-bg flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold">Your Agents</h1>
            <p className="text-sm text-axon-muted mt-1">
              {agents.length} agent{agents.length !== 1 ? "s" : ""} provisioned
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-axon-cyan text-axon-bg font-semibold text-sm hover:opacity-90 transition-colors"
          >
            <Plus size={14} />
            New agent
          </button>
        </div>

        {/* Create modal */}
        {showCreate && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-6">
            <div className="w-full max-w-md p-6 rounded-2xl border border-axon-border bg-axon-surface shadow-2xl">
              <div className="flex items-center justify-between mb-5">
                <h2 className="font-semibold">Provision new agent</h2>
                <button
                  onClick={() => setShowCreate(false)}
                  className="text-axon-muted hover:text-axon-text"
                >
                  <X size={16} />
                </button>
              </div>

              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="block text-xs text-axon-muted mb-1.5 font-mono uppercase tracking-wide">
                    Agent name
                  </label>
                  <input
                    autoFocus
                    className="w-full bg-axon-bg border border-axon-border rounded-lg px-4 py-2.5 text-sm text-axon-text placeholder-axon-muted"
                    placeholder="e.g. build-bot, data-cruncher"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs text-axon-muted mb-1.5 font-mono uppercase tracking-wide">
                    Description (optional)
                  </label>
                  <input
                    className="w-full bg-axon-bg border border-axon-border rounded-lg px-4 py-2.5 text-sm text-axon-text placeholder-axon-muted"
                    placeholder="What does this agent do?"
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                  />
                </div>
                <div className="pt-1 flex gap-3">
                  <button
                    type="button"
                    onClick={() => setShowCreate(false)}
                    className="flex-1 py-2.5 rounded-lg border border-axon-border text-sm text-axon-muted hover:text-axon-text hover:border-axon-muted transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={creating}
                    className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-axon-cyan text-axon-bg font-semibold text-sm hover:opacity-90 transition-colors disabled:opacity-60"
                  >
                    {creating && <Loader2 size={13} className="animate-spin" />}
                    {creating ? "Provisioning…" : "Provision"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Agents grid */}
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <Loader2 size={24} className="animate-spin text-axon-muted" />
          </div>
        ) : agents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <div className="p-4 rounded-2xl border border-axon-border bg-axon-surface mb-4">
              <Cpu size={28} className="text-axon-muted" />
            </div>
            <p className="text-sm text-axon-muted mb-4">No agents yet</p>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-axon-cyan text-axon-bg font-semibold text-sm hover:opacity-90 transition-colors"
            >
              <Plus size={14} />
              Provision your first agent
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                onStart={handleStart}
                onStop={handleStop}
                onDelete={handleDelete}
                loading={actionLoading}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
