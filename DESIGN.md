# AXON — Design & Architecture

**Live:** https://suryadeevi-dev.github.io/axon  
**API:** https://axon-api-lhjm.onrender.com  
**Repo:** https://github.com/suryadeevi-dev/axon

---

## 1. Concept

AXON gives every user a personal AI agent backed by a dedicated AWS EC2 instance. Users interact via chat — the agent reasons, writes code, executes shell commands via SSM Run Command, and streams results in real time.

Built entirely on permanent free tiers — no trial credits, no expiry (EC2/EBS are free for 12 months).

---

## 2. Architecture

```
  Browser (GitHub Pages — static)
    │
    ├─ HTTPS ──► Render (FastAPI)
    │             ├─ /api/auth/*           JWT + Google OAuth 2.0
    │             ├─ /api/agents/*         agent CRUD + start/stop + files
    │             ├─ /ws/agents/{id}       chat WebSocket (AI + SSM command loop)
    │             └─ /metrics              Prometheus metrics
    │
    ├─ DynamoDB (AWS us-east-1)    users / agents / messages
    │
    ├─ EC2 (AWS us-east-1a)
    │   └─ one instance per agent
    │        ├─ Ubuntu 22.04, t3.micro
    │        ├─ EBS gp3 8 GB — persistent /home/axon/workspace
    │        └─ SSM agent ← backend sends commands via Systems Manager
    │
    └─ S3 (AWS)                    agent file artifacts (AES-256, 30-day lifecycle)
```

### AWS networking

```
VPC: 10.0.0.0/16
  │
  └─ Public subnet: 10.0.1.0/24  (us-east-1a, map_public_ip=true)
       │
       └─ EC2 agent instances
            Security group: egress-only (0.0.0.0/0, all protocols)
            No inbound rules — SSM agent polls outbound HTTPS to ssm endpoint
            Public IP → internet access for apt/pip/agent tasks
```

### Agent turn data flow

1. User sends `{"type":"message","content":"..."}` over chat WebSocket
2. Backend loads last 20 messages from DynamoDB as conversation context
3. `ai_service.run_agent_turn()` opens a streaming Groq session
4. Every token streams to the browser as `{"type":"token","data":"..."}`
5. Model wraps shell commands in `<cmd>...</cmd>` tags inline in its response
6. Backend extracts tags → `{"type":"command","data":"..."}` → `ec2_service.exec_command()` via SSM
7. Command output sent as `{"type":"output","data":"..."}` → fed back as `<output>` context
8. Loop until model produces a pure-text response (no more `<cmd>` tags)
9. `{"type":"done"}` sent; assistant message persisted to DynamoDB

---

## 3. Key Design Decisions

### 3.1 EC2 per agent via SSM Run Command

Each agent maps to one EC2 instance. The backend never SSHes into instances — all command execution goes through SSM Run Command (`SendCommand` → poll `GetCommandInvocation`). The SSM agent inside the instance connects *outbound* to the Systems Manager HTTPS endpoint on `443`.

Instance lifecycle:
- **provision** → `RunInstances` + wait for SSM agent registration (~2–3 min on cold start)
- **stop** → `StopInstances` — EBS persists, compute billing pauses
- **start** → `StartInstances` + wait SSM re-registration (~30s on warm start)
- **terminate** → `TerminateInstances` — called on agent delete; EBS destroyed

The `container_id` field in DynamoDB stores the EC2 instance ID (`i-*`). Same field, different format from Docker container IDs — all upstream code treats it as an opaque string.

### 3.2 No inbound networking on agent instances

The security group on agent EC2 instances has zero inbound rules. This eliminates the entire attack surface of public SSH without needing a NAT Gateway or VPC endpoints. Outbound-all is required so the SSM agent can reach `ssm.us-east-1.amazonaws.com`, and so agent tasks can run `apt-get`, `pip install`, call APIs, etc.

### 3.3 IAM least privilege

Two IAM principals:

**EC2 instance profile** (`axon-agent-instance-role`):  
Attached `AmazonSSMManagedInstanceCore` only — enough for the SSM agent to register and receive `SendCommand` invocations.

**Backend IAM user** (`axon-backend`):

| Area | Operations | Scope |
|------|-----------|-------|
| EC2 launch | `RunInstances` | Instances tagged `Project=axon` |
| EC2 lifecycle | `Start/Stop/TerminateInstances` | Instances tagged `Project=axon` |
| EC2 read | `Describe*` | Unrestricted (read-only) |
| IAM | `PassRole` | `axon-agent-instance-role` ARN only |
| SSM | `SendCommand`, `GetCommandInvocation`, etc. | Unrestricted |
| S3 | `Get/Put/Delete/List` | `axon-agent-files-*` bucket only |
| DynamoDB | `GetItem/PutItem/UpdateItem/DeleteItem/Query` | `axon-*` table ARNs only |

### 3.4 S3 for agent file persistence

Agent workspace files that need to outlive instance stop/start cycles are stored in S3 under `agents/{agent_id}/`. The bucket has AES-256 SSE, all public access blocked, and a 30-day expiry lifecycle rule. Listed via `GET /api/agents/{id}/files`.

### 3.5 Compute fallback chain

Mode detected once at startup:

| Mode       | Condition                 | Isolation              | Use case     |
|------------|---------------------------|------------------------|--------------|
| EC2        | `EC2_ENABLED=true` + vars | Dedicated VM per agent | Production   |
| Docker     | Docker socket present      | Container per agent    | Local dev    |
| Subprocess | Fallback                  | Shared temp dir        | Demo / CI    |

### 3.6 Observability

**Structured JSON logs** — `_JsonFormatter` on the root logger emits every line as a JSON object. `RequestIDMiddleware` generates a 12-char hex ID per HTTP request, injects it into `contextvars.ContextVar`, and includes it in all log lines produced during that request. The ID is also echoed in `X-Request-ID` response header for client-side correlation.

**Prometheus metrics** — `prometheus_fastapi_instrumentator` auto-instruments HTTP handlers. Custom metrics cover the full agent lifecycle: WS connections, agent operations, AI token consumption, rate-limit fallbacks, sandbox provision latency, and command execution latency/success rate. Exposed at `/metrics` (not auto-instrumented to keep it clean).

**Grafana Cloud** — free forever tier (10K series, 50 GB logs) can scrape `/metrics` directly. Add `https://axon-api-lhjm.onrender.com/metrics` as a Prometheus data source.

### 3.7 Static frontend on GitHub Pages

Next.js `output: 'export'` generates a fully static site served free via GitHub's CDN. SPA routing is solved by copying the app shell to `404.html` — GitHub Pages serves it for unknown paths, React's client router takes over. Agent IDs are read from `window.location.pathname` because `useParams()` returns static build-time params on Pages.

### 3.8 Render for the backend

No infrastructure to manage, automatic deploys, free TLS. Spins down after 15 minutes of inactivity (~30s cold start on wake). A GitHub Actions cron keep-alive ping mitigates this. Single worker (`--workers 1`) because the in-memory DynamoDB fallback is not shared across processes.

### 3.9 AI: Groq + automatic rate-limit fallback

Groq provides Llama 3.3 70B at ~200 tokens/second on its free tier (100K TPD). When the daily limit is hit, the service automatically falls back to `llama-3.1-8b-instant` (500K TPD) with a brief notice. The `axon_ai_rate_limit_fallbacks_total` metric tracks frequency.

`<cmd>...</cmd>` tag extraction instead of native tool-calling: simpler, framework-agnostic, and the commands appear inline in the streamed token output so the UI renders them naturally.

### 3.10 DynamoDB + in-memory fallback

AWS credentials present → DynamoDB (always-free, permanent). No credentials → thread-safe in-memory dict (local dev). All features identical in both modes. `threading.Lock()` on all writes protects concurrent FastAPI workers.

### 3.11 Auth: JWT + bcrypt + Google OAuth

Custom JWT rather than Cognito/Auth0 — portable across any Python host. Google OAuth uses the backend Authorization Code flow (frontend redirects to `/api/auth/google`, backend handles the full dance). JWT is passed as `?token=` on WebSocket handshake (browsers don't support `Authorization` header on WS upgrades).

---

## 4. Free Tier Breakdown

| Service        | Role                           | Free Tier                        |
|----------------|--------------------------------|----------------------------------|
| GitHub Pages   | Frontend (Next.js static)      | Unlimited                        |
| Render         | Backend (FastAPI)              | 750 hrs/month                    |
| EC2 t3.micro   | Agent instances                | 750 hrs/month (first 12 months)  |
| EBS gp3        | Agent workspace (8 GB/agent)   | 30 GB total (first 12 months)    |
| S3             | Agent file artifacts           | 5 GB + 20K GET, 2K PUT/month     |
| DynamoDB       | users, agents, messages        | 25 GB + 25 WCU/RCU (permanent)   |
| Groq 70B       | Primary AI                     | 100K tokens/day                  |
| Groq 8B        | Rate-limit fallback AI         | 500K tokens/day                  |
| Google OAuth   | SSO                            | Unlimited                        |
| GitHub Actions | CI/CD + keep-alive cron        | 2000 min/month                   |

---

## 5. Security

- **No open ports on agent instances:** SSM requires zero inbound rules. No SSH, no bastion, no port 22.
- **IAM scoped by tag:** EC2 launch/lifecycle operations are conditioned on `Project=axon` tag.
- **Credentials never in code:** secrets live in Render's env vault or Terraform state (outputs marked `sensitive`).
- **JWT HS256:** strong random secret auto-generated per Render deployment.
- **Agent isolation:** each EC2 instance is a separate VM — no shared filesystem or process space between users.
- **S3:** AES-256 SSE, no public access, 30-day expiry.

---

## 6. UI

- **Brand:** dark engineering aesthetic — `#0a0a12` background, `#22d3ee` electric cyan, monospace accents
- **Light/dark mode:** `next-themes` with RGB CSS custom properties so Tailwind opacity modifiers (`/50`) work across themes
- **Agent page tabs:** Chat (streaming AI conversation + SSM command output), Resources (instance + model specs)
- **Responsive:** full-width mobile, max-width 4xl desktop
