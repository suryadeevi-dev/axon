"use client";

import { useEffect, useRef, useCallback } from "react";
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import { WebLinksAddon } from "xterm-addon-web-links";
import "xterm/css/xterm.css";
import { getToken } from "@/lib/auth";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

interface Props {
  agentId: string;
  sandboxReady: boolean;
}

export default function XTerminal({ agentId, sandboxReady }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef      = useRef<Terminal | null>(null);
  const fitRef       = useRef<FitAddon | null>(null);
  const wsRef        = useRef<WebSocket | null>(null);
  const connectedRef = useRef(false);

  const connect = useCallback(() => {
    if (!sandboxReady || connectedRef.current) return;
    const term = termRef.current;
    if (!term) return;

    const token = getToken();
    if (!token) return;

    const cols = term.cols || 80;
    const rows = term.rows || 24;
    const url  = `${WS_URL}/ws/agents/${agentId}/pty?token=${token}&cols=${cols}&rows=${rows}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      connectedRef.current = true;
      term.write("\r\n\x1b[32m● Connected to sandbox\x1b[0m\r\n\r\n");
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === "data") {
          term.write(atob(msg.data));
        } else if (msg.type === "error") {
          term.write(`\r\n\x1b[31m✗ ${msg.data}\x1b[0m\r\n`);
        }
      } catch {
        term.write(e.data);
      }
    };

    ws.onclose = () => {
      connectedRef.current = false;
      term.write("\r\n\x1b[33m● Disconnected\x1b[0m\r\n");
    };

    ws.onerror = () => {
      term.write("\r\n\x1b[31m● Connection error\x1b[0m\r\n");
    };

    // Keyboard input → PTY
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "input", data }));
      }
    });

    // Resize → PTY
    term.onResize(({ cols, rows }) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "resize", cols, rows }));
      }
    });
  }, [agentId, sandboxReady]);

  // Mount terminal
  useEffect(() => {
    if (!containerRef.current || termRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "'Geist Mono', 'SFMono-Regular', 'Menlo', monospace",
      theme: {
        background:   "#050508",
        foreground:   "#e2e8f0",
        cursor:       "#22d3ee",
        selectionBackground: "rgba(34,211,238,0.2)",
        black:        "#1e1e32",
        green:        "#34d399",
        cyan:         "#22d3ee",
        yellow:       "#fbbf24",
        red:          "#f87171",
        white:        "#e2e8f0",
        brightGreen:  "#6ee7b7",
        brightCyan:   "#67e8f9",
        brightWhite:  "#f8fafc",
      },
      scrollback: 2000,
      convertEol: true,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.loadAddon(new WebLinksAddon());
    term.open(containerRef.current);
    fitAddon.fit();

    termRef.current = term;
    fitRef.current  = fitAddon;

    term.write("\x1b[36mAXON Interactive Terminal\x1b[0m\r\n");
    term.write("Waiting for sandbox connection…\r\n");

    const ro = new ResizeObserver(() => fitAddon.fit());
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      wsRef.current?.close();
      term.dispose();
      termRef.current = null;
    };
  }, []);

  // Connect once sandbox is ready
  useEffect(() => {
    if (sandboxReady) connect();
  }, [sandboxReady, connect]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full"
      style={{ minHeight: "400px" }}
    />
  );
}
