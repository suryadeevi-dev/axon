"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, Server, Brain, Wrench, ShieldCheck, RefreshCw } from "lucide-react";
import { agentsApi } from "@/lib/api";

interface Props {
  sandboxReady: boolean;
  sandboxId?: string;
  agentId?: string;
}

interface S3File {
  key: string;
  size: number;
  last_modified: string;
}

function SectionCard({ icon, title, action, children }: { icon: React.ReactNode; title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-axon-border bg-axon-surface p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-axon-cyan">{icon}</span>
          <h3 className="text-sm font-semibold text-axon-text">{title}</h3>
        </div>
        {action}
      </div>
      <div className="space-y-2.5">{children}</div>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-xs text-axon-muted">{label}</span>
      <span className={`text-xs font-medium text-axon-text ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}

function Capability({ label, available }: { label: string; available: boolean }) {
  return (
    <div className="flex items-center gap-2">
      {available
        ? <CheckCircle2 size={13} className="text-axon-green shrink-0" />
        : <XCircle size={13} className="text-red-400/60 shrink-0" />}
      <span className={`text-xs ${available ? "text-axon-text" : "text-axon-muted/50 line-through"}`}>{label}</span>
    </div>
  );
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function ResourcesPanel({ sandboxReady, sandboxId, agentId }: Props) {
  const [files, setFiles] = useState<S3File[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [filesPath, setFilesPath] = useState<string | null>(null);

  const fetchFiles = async () => {
    if (!agentId) return;
    setLoadingFiles(true);
    try {
      const { data } = await agentsApi.files(agentId);
      setFiles(data.files ?? []);
      setFilesPath(data.path ?? null);
    } catch {
      // S3 not configured or agent not started — show empty
    } finally {
      setLoadingFiles(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, [agentId, sandboxReady]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6">
      <div className="max-w-2xl mx-auto space-y-4">

        <SectionCard icon={<Server size={16} />} title="Compute">
          <Row
            label="Status"
            value={
              <span className={`flex items-center gap-1.5 ${sandboxReady ? "text-axon-green" : "text-axon-muted"}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${sandboxReady ? "bg-axon-green animate-pulse" : "bg-axon-muted"}`} />
                {sandboxReady ? "Running" : "Stopped"}
              </span>
            }
          />
          {sandboxId && <Row label="Instance ID" value={sandboxId.slice(0, 19)} mono />}
          <Row label="Instance type" value="t3.micro" />
          <Row label="Provider" value="AWS EC2" />
          <Row label="OS" value="Ubuntu 22.04 LTS" />
          <Row label="vCPUs" value="2" />
          <Row label="RAM" value="1 GB" />
          <Row label="Storage" value="8 GB (EBS gp3)" />
          <Row label="Region" value="us-east-1" />
          <Row label="Command execution" value="SSM Run Command" />
        </SectionCard>

        <SectionCard icon={<Brain size={16} />} title="Model">
          <Row label="Model" value="Llama 3.3 70B Versatile" />
          <Row label="Provider" value="Groq" />
          <Row label="Context window" value="128K tokens" />
          <Row label="Max output" value="32,768 tokens" />
          <Row label="Speed" value="~200 tokens/sec" />
        </SectionCard>

        <SectionCard icon={<Wrench size={16} />} title="Capabilities">
          <Capability label="Shell access (bash, sh)" available />
          <Capability label="File read / write / edit" available />
          <Capability label="Package install (apt, pip, npm)" available />
          <Capability label="Python / Node.js runtimes" available />
          <Capability label="Outbound network access" available />
          <Capability label="S3 workspace file storage" available />
          <Capability label="Interactive terminal (xterm.js)" available={false} />
          <Capability label="Web browsing (Playwright)" available={false} />
          <Capability label="Screenshots / GUI desktop" available={false} />
          <Capability label="Persistent memory across sessions" available={false} />
        </SectionCard>

        <SectionCard icon={<ShieldCheck size={16} />} title="Security">
          <Row label="Inbound ports" value="None (SSM outbound only)" />
          <Row label="Network" value="Outbound only" />
          <Row label="Isolation" value="Dedicated EC2 instance" />
          <Row label="Data" value="Private to your account" />
          <Row label="IAM" value="SSM + S3 scoped" />
        </SectionCard>

        <SectionCard
          icon={<Server size={16} />}
          title="Workspace Files"
          action={
            <button
              onClick={fetchFiles}
              disabled={loadingFiles}
              className="p-1 rounded text-axon-muted hover:text-axon-text transition-colors disabled:opacity-40"
              title="Refresh"
            >
              <RefreshCw size={12} className={loadingFiles ? "animate-spin" : ""} />
            </button>
          }
        >
          {files.length === 0 ? (
            <p className="text-xs text-axon-muted">
              {sandboxReady ? "No files yet — run a command to generate output." : "Start the agent to see workspace files."}
            </p>
          ) : (
            <>
              {filesPath && <p className="text-[10px] text-axon-muted font-mono mb-1 break-all">{filesPath}</p>}
              <div className="space-y-1.5">
                {files.map((f) => (
                  <div key={f.key} className="flex items-center justify-between gap-2">
                    <span className="text-xs font-mono text-axon-text truncate">{f.key}</span>
                    <span className="text-[10px] text-axon-muted shrink-0">{formatBytes(f.size)}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </SectionCard>

      </div>
    </div>
  );
}
