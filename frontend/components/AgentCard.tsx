"use client";

import Link from "next/link";
import { Cpu, CircleDot, Square, Trash2, Play } from "lucide-react";

interface Agent {
  id: string;
  name: string;
  description?: string;
  status: "running" | "stopped" | "starting" | "error";
  created_at: string;
  last_active?: string;
}

interface Props {
  agent: Agent;
  onStart: (id: string) => void;
  onStop: (id: string) => void;
  onDelete: (id: string) => void;
  loading?: string | null;
}

const STATUS_COLORS = {
  running: "bg-axon-green text-axon-bg",
  stopped: "bg-axon-muted text-white",
  starting: "bg-yellow-400 text-axon-bg animate-pulse",
  error: "bg-red-500 text-white",
};

const STATUS_DOT = {
  running: "bg-axon-green",
  stopped: "bg-axon-muted",
  starting: "bg-yellow-400 animate-pulse",
  error: "bg-red-500",
};

export default function AgentCard({ agent, onStart, onStop, onDelete, loading }: Props) {
  const isLoading = loading === agent.id;

  return (
    <div className="group p-5 rounded-xl border border-axon-border bg-axon-surface hover:border-axon-muted transition-all animate-slide-up">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-axon-bg border border-axon-border">
            <Cpu size={16} className="text-axon-cyan" />
          </div>
          <div>
            <h3 className="font-semibold text-sm">{agent.name}</h3>
            {agent.description && (
              <p className="text-xs text-axon-muted mt-0.5">{agent.description}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-axon-border text-xs">
          <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[agent.status]}`} />
          {agent.status}
        </div>
      </div>

      <div className="text-xs text-axon-muted font-mono mb-4">
        ID: {agent.id.slice(0, 12)}…
        {agent.last_active && (
          <span className="ml-3">
            active {new Date(agent.last_active).toLocaleDateString()}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        {agent.status === "running" ? (
          <Link
            href={`/agent/${agent.id}`}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-axon-cyan text-axon-bg font-semibold text-xs hover:bg-white transition-colors"
          >
            <CircleDot size={12} />
            Open chat
          </Link>
        ) : (
          <button
            onClick={() => onStart(agent.id)}
            disabled={isLoading}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-axon-cyan/10 border border-axon-cyan/30 text-axon-cyan text-xs font-medium hover:bg-axon-cyan/20 transition-colors disabled:opacity-50"
          >
            <Play size={12} />
            {isLoading ? "Starting…" : "Start agent"}
          </button>
        )}

        {agent.status === "running" && (
          <button
            onClick={() => onStop(agent.id)}
            disabled={isLoading}
            className="p-2 rounded-lg border border-axon-border text-axon-muted hover:text-white hover:border-axon-muted transition-colors disabled:opacity-50"
            title="Stop"
          >
            <Square size={12} />
          </button>
        )}

        <button
          onClick={() => onDelete(agent.id)}
          disabled={isLoading}
          className="p-2 rounded-lg border border-axon-border text-axon-muted hover:text-red-400 hover:border-red-400/30 transition-colors disabled:opacity-50"
          title="Delete"
        >
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  );
}
