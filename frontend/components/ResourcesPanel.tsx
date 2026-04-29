"use client";

import { CheckCircle2, XCircle, Server, Brain, Wrench, ShieldCheck } from "lucide-react";

interface Props {
  sandboxReady: boolean;
  sandboxId?: string;
}

function SectionCard({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-axon-border bg-axon-surface p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-axon-cyan">{icon}</span>
        <h3 className="text-sm font-semibold text-axon-text">{title}</h3>
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

export default function ResourcesPanel({ sandboxReady, sandboxId }: Props) {
  return (
    <div className="flex-1 overflow-y-auto px-6 py-6">
      <div className="max-w-2xl mx-auto space-y-4">

        <SectionCard icon={<Server size={16} />} title="Sandbox">
          <Row
            label="Status"
            value={
              <span className={`flex items-center gap-1.5 ${sandboxReady ? "text-axon-green" : "text-axon-muted"}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${sandboxReady ? "bg-axon-green" : "bg-axon-muted"}`} />
                {sandboxReady ? "Online" : "Offline"}
              </span>
            }
          />
          {sandboxId && <Row label="Sandbox ID" value={sandboxId.slice(0, 16) + "…"} mono />}
          <Row label="Instance" value="E2B Micro" />
          <Row label="Provider" value="e2b.dev" />
          <Row label="OS" value="Ubuntu 22.04 LTS" />
          <Row label="vCPUs" value="2" />
          <Row label="RAM" value="512 MB" />
          <Row label="Storage" value="5 GB" />
          <Row label="Region" value="us-east-1" />
          <Row label="Session timeout" value="1 hour" />
        </SectionCard>

        <SectionCard icon={<Brain size={16} />} title="Model">
          <Row label="Model" value="Llama 3.3 70B Versatile" />
          <Row label="Provider" value="Groq" />
          <Row label="Context window" value="128K tokens" />
          <Row label="Max output" value="32,768 tokens" />
          <Row label="Latency" value="~200 tokens/sec" />
        </SectionCard>

        <SectionCard icon={<Wrench size={16} />} title="Capabilities">
          <Capability label="Shell access (bash, sh)" available />
          <Capability label="File read / write / edit" available />
          <Capability label="Package install (apt, pip, npm)" available />
          <Capability label="Python / Node.js / Go runtimes" available />
          <Capability label="Outbound network access" available />
          <Capability label="Interactive terminal (xterm.js)" available />
          <Capability label="Web browsing (Playwright)" available={false} />
          <Capability label="Screenshots / GUI desktop" available={false} />
          <Capability label="Image generation" available={false} />
          <Capability label="Persistent memory across sessions" available={false} />
        </SectionCard>

        <SectionCard icon={<ShieldCheck size={16} />} title="Permissions">
          <Row label="AWS access" value="None" />
          <Row label="Network" value="Outbound only" />
          <Row label="Isolation" value="Dedicated E2B sandbox" />
          <Row label="Data" value="Private to your account" />
          <Row label="Sandbox reuse" value="Reconnected per session" />
        </SectionCard>

      </div>
    </div>
  );
}
