# AXON — Design & Architecture

**Live:** https://suryadeevi-dev.github.io/axon  
**API:** https://axon-api-lhjm.onrender.com  
**Repo:** https://github.com/suryadeevi-dev/axon

---

## 1. Concept

AXON gives every user a personal AI agent backed by a dedicated cloud sandbox. Users interact via chat — the agent reasons, writes code, executes commands, and streams results in real time. The Terminal tab provides a full interactive PTY connected directly to the sandbox for hands-on access.

Built entirely on permanent free tiers — no trial credits, no expiry.

---

## 2. Architecture

```
  Browser (GitHub Pages — static)
    │
    ├─ HTTPS ──► Render (FastAPI)
    │             ├─ /api/auth/*           JWT + Google OAuth 2.0
    │             ├─ /api/agents/*         agent CRUD + start/stop + files
    │             ├─ /ws/agents/{id}       chat WebSocket (AI + command loop)
    │             └─ /ws/agents/{id}/pty   PTY WebSocket (xterm.js ↔ E2B)
    │
    ├─ DynamoDB (AWS us-east-1)    users / agents / messages
    │
    └─ E2B (e2b.dev)               isolated Ubuntu 22.04 sandboxes
```

### Agent turn data flow
1. User sends `{"type":"message","content":"..."}` over chat WebSocket
2. Backend loads last 20 messages from DynamoDB as conversation context
3. `ai_service.run_agent_turn()` opens a streaming Groq session
4. Every token streams to the browser as `{"type":"token","data":"..."}`
5. Model wraps shell commands in `<cmd>...</cmd>` tags inline in its response
6. Backend extracts tags → sends `{"type":"command","data":"..."}` → executes in E2B sandbox
7. Command output sent as `{"type":"output","data":"..."}` → fed back as `<output>` context
8. Loop repeats until the model produces a pure-text response (no `<cmd>` tags)
9. `{"type":"done"}` signals completion; assistant message persisted to DynamoDB

---

## 3. Key Design Decisions

### 3.1 Static frontend on GitHub Pages

Next.js `output: 'export'` generates a fully static site. GitHub Pages serves it free via GitHub's CDN with zero cold-start. The SPA routing problem (GitHub Pages returns 404 for unknown deep-links) is solved by copying the app shell to `404.html` in the build pipeline — GitHub Pages serves it for any unknown path, and React's client-side router takes over.

`useParams()` returns static build-time params (`id: "new"`) on GitHub Pages. Agent IDs are read from `window.location.pathname` instead.

### 3.2 Render for the backend

No infrastructure to manage, automatic deploys from git, free TLS. Spins down after 15 minutes of inactivity (~30s cold start on wake). A GitHub Actions cron keep-alive ping mitigates this during active hours.

### 3.3 AI: Groq + automatic fallback

Groq provides Llama 3.3 70B on its free tier at ~200 tokens/second — faster than most paid providers. The free tier caps at 100K tokens per day. When that limit is hit, the service automatically falls back to `llama-3.1-8b-instant` (500K TPD) with a brief notice to the user. No interruption to the session.

`<cmd>...</cmd>` tag extraction is used instead of the model's native tool-calling. This keeps the reasoning and the commands in the same token stream, is framework-agnostic, and is simpler to debug.

### 3.4 Compute: E2B → Docker → Subprocess

Three modes, checked automatically at startup:

| Mode       | Condition               | Isolation        |
|------------|-------------------------|------------------|
| E2B        | `E2B_API_KEY` set       | Dedicated VM per agent |
| Docker     | Docker socket available | Container per agent    |
| Subprocess | Fallback                | Shared temp dir (demo) |

E2B is the production path: a real isolated Ubuntu 22.04 VM per agent, provisioned on first use. The sandbox ID is stored as `container_id` on the agent record. On reconnect, `Sandbox.connect(sandbox_id)` resumes the existing sandbox. When it expires, a new sandbox is provisioned and the new ID is written back to the DB.

### 3.5 DynamoDB + in-memory fallback

The backend detects AWS credentials at startup:

- **Credentials present** → DynamoDB (production path; always-free tier, no expiry)
- **No credentials** → thread-safe in-memory dict (local dev / demo)

All features work identically in both modes. The in-memory store uses `threading.Lock()` on all writes for safety under FastAPI's async workers.

The Render service account (`axon-prod`) holds a least-privilege IAM policy — only `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem`, `Query` on the three specific table ARNs. No `CreateTable`, no access to any other AWS service.

### 3.6 Interactive terminal: xterm.js PTY over WebSocket

A dedicated `/ws/agents/{id}/pty` endpoint bridges the browser terminal to the E2B sandbox PTY.

**Protocol:**
- Browser → server: `{"type":"input","data":"..."}` (keystrokes), `{"type":"resize","cols":n,"rows":n}`
- Server → browser: `{"type":"data","data":"<base64>"}` (raw PTY output, base64-encoded), `{"type":"ping"}` (30s keepalive)

Base64 encoding is used because PTY output is binary (ANSI escape codes, control characters) and must be safely carried inside JSON.

**AsyncSandbox required:** In e2b 1.x, the `on_data` callback is only accepted by `AsyncSandbox.pty.create()`, not the sync `Sandbox`. The PTY service uses `AsyncSandbox` directly (no `asyncio.to_thread` wrapper) and unwraps `PtyOutput.data` bytes before forwarding.

**Sandbox lifecycle:** When an agent is stopped or deleted, `kill_sandbox(container_id)` is called to immediately teardown the E2B VM. This keeps E2B free-tier hours from being wasted on abandoned sandboxes.

### 3.7 Auth: JWT + bcrypt + Google OAuth

Custom JWT auth rather than Cognito or Auth0. JWT+bcrypt is portable — works on Render, locally, or any Python host with no external dependency. Google OAuth uses the backend Authorization Code flow: the frontend redirects to `/api/auth/google`, the backend handles the full OAuth dance, and issues a JWT cookie on success.

---

## 4. Free Tier Breakdown

| Service      | Role                           | Free Tier                      |
|--------------|--------------------------------|--------------------------------|
| GitHub Pages | Frontend (Next.js static)      | Unlimited                      |
| Render       | Backend (FastAPI)              | 750 hrs/month                  |
| E2B          | Agent sandboxes                | 100 hrs/month                  |
| DynamoDB     | users, agents, messages        | 25 GB + 25 WCU/RCU (permanent) |
| Groq         | Llama 3.3 70B (primary AI)     | 100K tokens/day                |
| Groq         | Llama 3.1 8B (fallback AI)     | 500K tokens/day                |
| Google OAuth | SSO                            | Unlimited                      |
| GitHub Actions | CI/CD + keep-alive cron      | 2000 min/month                 |

---

## 5. Security

- **IAM least privilege:** `axon-prod` has only the 5 DynamoDB operations it needs, scoped to the 3 specific table ARNs. No wildcard resources.
- **Credentials never in code:** all secrets in Render environment (secrets vault), `.env` gitignored.
- **JWT signing:** HS256 with a strong random secret generated per deployment.
- **Sandbox isolation:** each agent's E2B sandbox is a separate VM — no shared filesystem, no shared process space between users.
- **WebSocket auth:** JWT passed as `?token=` query param on WS handshake (browsers don't support `Authorization` header on WebSocket upgrades).

---

## 6. UI

- **Brand:** dark engineering aesthetic — `#0a0a12` background, `#22d3ee` electric cyan, monospace accents
- **Light/dark mode:** `next-themes` with CSS custom properties using RGB channels (`--axon-cyan: 34 211 238`) so Tailwind's opacity modifier (`/50`) works across themes
- **Agent page tabs:** Chat (streaming AI conversation), Terminal (live xterm.js PTY), Resources (sandbox + model specs)
- **Responsive:** full-width on mobile, max-width 4xl on desktop
