"use client";

import Link from "next/link";
import { Terminal, Zap, Shield, Cpu, ArrowRight, CheckCircle2 } from "lucide-react";

const FEATURES = [
  {
    icon: Cpu,
    title: "Dedicated Compute",
    desc: "Each agent runs in its own isolated container with full Linux environment. No shared resources, no noisy neighbors.",
  },
  {
    icon: Terminal,
    title: "Execute Anything",
    desc: "Run bash commands, install packages, write and run code — your agent has a full shell and persistent filesystem.",
  },
  {
    icon: Zap,
    title: "Real-time Streaming",
    desc: "Watch command output stream live. No waiting for batch responses — every token and every line, as it happens.",
  },
  {
    icon: Shield,
    title: "Isolated & Secure",
    desc: "Container-level isolation with network policies. Your agent's environment is yours alone, sandboxed from others.",
  },
];

const TERMINAL_LINES = [
  { type: "prompt", text: "axon@node-7f2a:~$ " },
  { type: "cmd", text: "git clone https://github.com/you/project && cd project" },
  { type: "out", text: "Cloning into 'project'..." },
  { type: "out", text: "remote: Enumerating objects: 142, done." },
  { type: "prompt", text: "axon@node-7f2a:~/project$ " },
  { type: "cmd", text: "pip install -r requirements.txt && python main.py" },
  { type: "out", text: "Successfully installed 23 packages" },
  { type: "out", text: "Server running on 0.0.0.0:8080" },
];

export default function LandingPage() {
  return (
    <div
      className="min-h-screen bg-axon-bg"
      style={{
        backgroundImage:
          "linear-gradient(rgba(0,212,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.025) 1px, transparent 1px)",
        backgroundSize: "32px 32px",
      }}
    >
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-axon-border bg-axon-bg/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <span className="font-mono text-xl font-semibold tracking-wider text-axon-text">
            AX<span className="text-axon-cyan">ON</span>
          </span>
          <div className="flex items-center gap-4">
            <Link
              href="/login"
              className="text-sm text-axon-muted hover:text-white transition-colors"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="text-sm px-4 py-1.5 rounded-md bg-axon-cyan text-axon-bg font-semibold hover:bg-white transition-colors"
            >
              Get started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-20 px-6">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(ellipse 70% 40% at 50% 0%, rgba(0,212,255,0.12), transparent)",
          }}
        />
        <div className="relative max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-axon-border bg-axon-surface text-xs text-axon-muted mb-8 font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-axon-green animate-pulse" />
            Now in early access — limited capacity
          </div>

          <h1 className="text-5xl sm:text-7xl font-bold leading-[1.05] mb-6 tracking-tight">
            Your agent.
            <br />
            <span className="text-axon-cyan" style={{ textShadow: "0 0 40px rgba(0,212,255,0.4)" }}>
              Your cloud.
            </span>
          </h1>

          <p className="text-lg sm:text-xl text-axon-muted max-w-2xl mx-auto mb-10 leading-relaxed">
            AXON gives you a personal AI agent backed by dedicated cloud compute.
            Chat with it in plain language — it writes code, runs commands, and
            gets real work done on its own Linux environment.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/signup"
              className="flex items-center gap-2 px-7 py-3.5 rounded-lg bg-axon-cyan text-axon-bg font-semibold text-base hover:bg-white transition-all hover:scale-[1.02] glow-cyan"
            >
              Launch your agent <ArrowRight size={16} />
            </Link>
            <Link
              href="/login"
              className="flex items-center gap-2 px-7 py-3.5 rounded-lg border border-axon-border text-axon-text text-base hover:border-axon-muted transition-colors"
            >
              Sign in
            </Link>
          </div>
        </div>
      </section>

      {/* Terminal demo */}
      <section className="px-6 pb-24">
        <div className="max-w-3xl mx-auto">
          <div className="rounded-xl border border-axon-border overflow-hidden shadow-2xl">
            {/* Window chrome */}
            <div className="flex items-center gap-2 px-4 py-3 bg-axon-surface border-b border-axon-border">
              <span className="w-3 h-3 rounded-full bg-[#ff5f57]" />
              <span className="w-3 h-3 rounded-full bg-[#febc2e]" />
              <span className="w-3 h-3 rounded-full bg-[#28c840]" />
              <span className="ml-3 text-xs font-mono text-axon-muted">
                axon — agent-node-7f2a — bash
              </span>
            </div>
            {/* Terminal body */}
            <div className="bg-[#050508] p-5 font-mono text-sm leading-relaxed min-h-[200px]">
              {TERMINAL_LINES.map((line, i) => (
                <div key={i} className="flex gap-0">
                  {line.type === "prompt" && (
                    <span className="text-axon-cyan">{line.text}</span>
                  )}
                  {line.type === "cmd" && (
                    <span className="text-axon-text">{line.text}</span>
                  )}
                  {line.type === "out" && (
                    <span className="text-axon-muted">{line.text}</span>
                  )}
                </div>
              ))}
              <div className="flex items-center gap-0 mt-1">
                <span className="text-axon-cyan">axon@node-7f2a:~/project$ </span>
                <span className="w-2 h-4 bg-axon-cyan ml-0.5 animate-[cursor-blink_1s_step-end_infinite]" />
              </div>
            </div>
          </div>
          <p className="text-center text-xs text-axon-muted mt-3 font-mono">
            Real shell. Real compute. Yours.
          </p>
        </div>
      </section>

      {/* Features */}
      <section className="px-6 pb-24">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-center text-3xl font-bold mb-2">
            Built for real work
          </h2>
          <p className="text-center text-axon-muted mb-12">
            Not a chatbot. A compute platform you talk to.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="p-6 rounded-xl border border-axon-border bg-axon-surface hover:border-axon-muted transition-colors group"
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 rounded-lg bg-axon-bg border border-axon-border group-hover:border-axon-cyan/30 transition-colors">
                    <f.icon size={18} className="text-axon-cyan" />
                  </div>
                  <h3 className="font-semibold">{f.title}</h3>
                </div>
                <p className="text-sm text-axon-muted leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="px-6 pb-24">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-center text-3xl font-bold mb-12">
            How it works
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
            {[
              {
                step: "01",
                title: "Create an account",
                desc: "Sign up and get instant access to the AXON platform.",
              },
              {
                step: "02",
                title: "Provision your agent",
                desc: "One click spins up your agent and its dedicated Linux container.",
              },
              {
                step: "03",
                title: "Chat & execute",
                desc: "Describe what you want. Your agent writes code, runs commands, and reports back live.",
              },
            ].map((item) => (
              <div key={item.step} className="text-center">
                <div className="text-4xl font-mono font-bold text-axon-cyan/20 mb-3">
                  {item.step}
                </div>
                <h3 className="font-semibold mb-2">{item.title}</h3>
                <p className="text-sm text-axon-muted leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 pb-24">
        <div className="max-w-2xl mx-auto text-center p-12 rounded-2xl border border-axon-border bg-axon-surface relative overflow-hidden">
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                "radial-gradient(ellipse 60% 60% at 50% 50%, rgba(0,212,255,0.06), transparent)",
            }}
          />
          <h2 className="relative text-3xl font-bold mb-3">
            Ready to deploy your agent?
          </h2>
          <p className="relative text-axon-muted mb-8">
            Free tier available. No credit card required.
          </p>
          <Link
            href="/signup"
            className="relative inline-flex items-center gap-2 px-8 py-3.5 rounded-lg bg-axon-cyan text-axon-bg font-semibold hover:bg-white transition-all hover:scale-[1.02] glow-cyan"
          >
            Get started — it&apos;s free <ArrowRight size={16} />
          </Link>
          <div className="relative mt-6 flex items-center justify-center gap-6 text-xs text-axon-muted">
            {["No setup fees", "Free tier always available", "Deploy in under 60s"].map((t) => (
              <span key={t} className="flex items-center gap-1">
                <CheckCircle2 size={12} className="text-axon-green" />
                {t}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-axon-border px-6 py-8">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <span className="font-mono text-sm font-semibold tracking-wider text-axon-muted">
            AX<span className="text-axon-cyan">ON</span>
          </span>
          <p className="text-xs text-axon-muted">
            © 2026 AXON. Autonomous agents, dedicated compute.
          </p>
        </div>
      </footer>
    </div>
  );
}
