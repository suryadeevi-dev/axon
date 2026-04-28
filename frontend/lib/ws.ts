import { getToken } from "./auth";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  type?: "text" | "command" | "output" | "error";
}

export interface WSEvent {
  type: "message" | "token" | "command" | "output" | "error" | "status" | "done";
  data: string | Record<string, unknown>;
  message_id?: string;
}

export class AgentWebSocket {
  private ws: WebSocket | null = null;
  private agentId: string;
  private onEvent: (event: WSEvent) => void;
  private onStatusChange: (connected: boolean) => void;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private maxReconnects = 5;

  constructor(
    agentId: string,
    onEvent: (event: WSEvent) => void,
    onStatusChange: (connected: boolean) => void
  ) {
    this.agentId = agentId;
    this.onEvent = onEvent;
    this.onStatusChange = onStatusChange;
  }

  connect() {
    const token = getToken();
    const url = `${WS_URL}/ws/agents/${this.agentId}?token=${token}`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.onStatusChange(true);
    };

    this.ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as WSEvent;
        this.onEvent(event);
      } catch {
        // ignore malformed
      }
    };

    this.ws.onerror = () => {
      this.onStatusChange(false);
    };

    this.ws.onclose = () => {
      this.onStatusChange(false);
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnects) return;
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 15000);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  send(text: string) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "message", content: text }));
    }
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.maxReconnects = 0;
    this.ws?.close();
    this.ws = null;
  }
}
