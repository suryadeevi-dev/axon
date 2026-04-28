"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { ArrowLeft, Send, Loader2, Terminal, MessageSquare, RotateCcw } from "lucide-react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { AgentWebSocket, ChatMessage, WSEvent } from "@/lib/ws";
import { agentsApi } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import toast from "react-hot-toast";

type Tab = "chat" | "terminal";

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  const isSystem = msg.role === "system";

  if (isSystem) {
    return (
      <div className="text-center py-1">
        <span className="text-xs text-axon-muted font-mono px-3 py-0.5 rounded-full border border-axon-border bg-axon-surface">
          {msg.content}
        </span>
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} animate-slide-up`}>
      <div className={`max-w-[78%] ${isUser ? "order-2" : "order-1"}`}>
        {msg.type === "command" || msg.type === "output" ? (
          <div className="rounded-xl border border-axon-border bg-[#050508] p-3 font-mono text-xs">
            {msg.type === "command" && (
              <div className="flex items-center gap-1.5 mb-1.5 text-axon-cyan">
                <span className="text-axon-muted">$</span>
                <span>{msg.content}</span>
              </div>
            )}
            {msg.type === "output" && (
              <pre className="text-axon-green whitespace-pre-wrap break-all leading-relaxed">
                {msg.content}
              </pre>
            )}
          </div>
        ) : (
          <div
            className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
              isUser
                ? "bg-axon-cyan text-axon-bg rounded-br-sm"
                : "bg-axon-surface border border-axon-border text-axon-text rounded-bl-sm"
            }`}
          >
            {msg.content}
          </div>
        )}
        <div className={`text-[10px] text-axon-muted mt-1 ${isUser ? "text-right" : "text-left"}`}>
          {formatTime(msg.timestamp)}
        </div>
      </div>
    </div>
  );
}

export default function AgentPageClient() {
  const router = useRouter();
  const params = useParams();
  const agentId = params?.id as string;

  const [agentName, setAgentName] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [terminalLines, setTerminalLines] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("chat");

  const wsRef = useRef<AgentWebSocket | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const terminalEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const streamingMsgRef = useRef<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    if (!agentId) return;
    loadAgent();
    connectWS();
    return () => wsRef.current?.disconnect();
  }, [agentId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [terminalLines]);

  const loadAgent = async () => {
    try {
      const { data } = await agentsApi.get(agentId);
      setAgentName(data.agent.name);
      if (data.history?.length) setMessages(data.history);
    } catch {
      toast.error("Failed to load agent");
      router.push("/dashboard");
    }
  };

  const handleWSEvent = useCallback((event: WSEvent) => {
    const now = new Date().toISOString();
    switch (event.type) {
      case "token": {
        const token = event.data as string;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.type === "text" && streamingMsgRef.current === last.id) {
            return [...prev.slice(0, -1), { ...last, content: last.content + token }];
          }
          const newMsg: ChatMessage = { id: `msg-${Date.now()}`, role: "assistant", type: "text", content: token, timestamp: now };
          streamingMsgRef.current = newMsg.id;
          return [...prev, newMsg];
        });
        break;
      }
      case "command": {
        const cmd = event.data as string;
        setMessages((prev) => [...prev, { id: `cmd-${Date.now()}`, role: "assistant", type: "command", content: cmd, timestamp: now }]);
        setTerminalLines((prev) => [...prev, `$ ${cmd}`]);
        streamingMsgRef.current = null;
        break;
      }
      case "output": {
        const out = event.data as string;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.type === "output") return [...prev.slice(0, -1), { ...last, content: last.content + out }];
          return [...prev, { id: `out-${Date.now()}`, role: "assistant", type: "output", content: out, timestamp: now }];
        });
        setTerminalLines((prev) => [...prev, out]);
        streamingMsgRef.current = null;
        break;
      }
      case "done":
        setSending(false);
        streamingMsgRef.current = null;
        break;
      case "error":
        toast.error(typeof event.data === "string" ? event.data : "Agent error");
        setSending(false);
        break;
    }
  }, []);

  const connectWS = () => {
    wsRef.current?.disconnect();
    if (!agentId) return;
    wsRef.current = new AgentWebSocket(agentId, handleWSEvent, setWsConnected);
    wsRef.current.connect();
  };

  const sendMessage = () => {
    const text = input.trim();
    if (!text || sending) return;
    setSending(true);
    setInput("");
    streamingMsgRef.current = null;
    const userMsg: ChatMessage = { id: `user-${Date.now()}`, role: "user", type: "text", content: text, timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    wsRef.current?.send(text);
    inputRef.current?.focus();
  };

  if (!agentId) return null;

  return (
    <div className="min-h-screen bg-axon-bg flex flex-col">
      <Navbar />
      <div className="border-b border-axon-border px-6 py-3 flex items-center gap-4 bg-axon-surface">
        <Link href="/dashboard" className="text-axon-muted hover:text-axon-text transition-colors">
          <ArrowLeft size={16} />
        </Link>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${wsConnected ? "bg-axon-green" : "bg-red-500"}`} />
          <span className="font-semibold text-sm">{agentName || "Agent"}</span>
          <span className="text-xs text-axon-muted font-mono">{agentId?.slice(0, 8)}</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-axon-muted">{wsConnected ? "Connected" : "Reconnecting…"}</span>
          <button onClick={connectWS} className="p-1.5 rounded text-axon-muted hover:text-axon-text" title="Reconnect">
            <RotateCcw size={12} />
          </button>
        </div>
      </div>

      <div className="flex border-b border-axon-border bg-axon-bg px-6">
        {(["chat", "terminal"] as Tab[]).map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${activeTab === tab ? "border-axon-cyan text-axon-cyan" : "border-transparent text-axon-muted hover:text-axon-text"}`}
          >
            {tab === "chat" ? <MessageSquare size={12} /> : <Terminal size={12} />}
            {tab === "chat" ? "Chat" : "Terminal"}
          </button>
        ))}
      </div>

      <div className="flex-1 flex flex-col min-h-0 max-w-4xl mx-auto w-full">
        {activeTab === "chat" ? (
          <>
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-3">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-center pt-12">
                  <div className="p-4 rounded-2xl border border-axon-border bg-axon-surface mb-3">
                    <Terminal size={24} className="text-axon-cyan" />
                  </div>
                  <p className="text-sm font-medium mb-1">Agent ready</p>
                  <p className="text-xs text-axon-muted max-w-xs">Ask your agent to run code, install packages, query APIs, or anything a Linux shell can do.</p>
                  <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-sm">
                    {["Write and run a Python hello world", "Check available disk space", "Clone a GitHub repo and list its files", "Install and run htop"].map((s) => (
                      <button key={s} onClick={() => { setInput(s); inputRef.current?.focus(); }}
                        className="text-left px-3 py-2 rounded-lg border border-axon-border bg-axon-surface text-xs text-axon-muted hover:text-axon-text hover:border-axon-muted transition-colors"
                      >{s}</button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map((msg) => <MessageBubble key={msg.id} msg={msg} />)}
              {sending && <div className="flex gap-2 items-center text-axon-muted text-xs animate-pulse"><Loader2 size={12} className="animate-spin" />Agent thinking…</div>}
              <div ref={chatEndRef} />
            </div>
            <div className="border-t border-axon-border px-6 py-4">
              <div className="flex items-center gap-3 rounded-xl border border-axon-border bg-axon-surface px-4 py-2.5 focus-within:border-axon-cyan/50 transition-colors">
                <input ref={inputRef}
                  className="flex-1 bg-transparent text-sm text-axon-text placeholder-axon-muted outline-none"
                  placeholder="Tell your agent what to do…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
                  disabled={!wsConnected}
                />
                <button onClick={sendMessage} disabled={!input.trim() || sending || !wsConnected}
                  className="p-1.5 rounded-lg bg-axon-cyan text-axon-bg hover:bg-white transition-colors disabled:opacity-40">
                  <Send size={14} />
                </button>
              </div>
              <p className="text-[10px] text-axon-muted mt-1.5 pl-1">Enter to send · Shift+Enter for newline</p>
            </div>
          </>
        ) : (
          <div className="flex-1 overflow-y-auto bg-[#050508] p-5 font-mono text-xs leading-relaxed">
            {terminalLines.length === 0 ? (
              <div className="text-axon-muted">
                <span className="text-axon-cyan">axon@node:{agentId?.slice(0, 6)}$ </span>
                <span className="animate-[cursor-blink_1s_step-end_infinite] inline-block w-2 h-3 bg-axon-cyan ml-0.5 align-middle" />
                <br /><span className="text-axon-muted/60">No output yet. Send a message in the Chat tab.</span>
              </div>
            ) : (
              <>
                {terminalLines.map((line, i) => (
                  <div key={i} className={line.startsWith("$") ? "text-axon-cyan mt-2" : "text-axon-green"}>{line}</div>
                ))}
                <div className="flex items-center mt-2">
                  <span className="text-axon-cyan">axon@node:{agentId?.slice(0, 6)}$ </span>
                  <span className="inline-block w-2 h-3 bg-axon-cyan ml-0.5 align-middle animate-[cursor-blink_1s_step-end_infinite]" />
                </div>
              </>
            )}
            <div ref={terminalEndRef} />
          </div>
        )}
      </div>
    </div>
  );
}
