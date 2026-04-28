# AXON — Design & Architecture Document

## Summary

**Repo:** https://github.com/suryadeevi-dev/axon  
**Live URL:** https://suryadeevi-dev.github.io/axon/  
**Backend deploy:** `render.yaml` included — one-click from Render dashboard  
**AWS CDK stack:** `infra/stacks/axon_stack.py` — production-grade free-tier deployment

---

## 1. What SkyKoi Is (Reverse-Engineered)

SkyKoi's gated landing says "Your Own Koi With Its Own Computer." The core concept I inferred:

- Each user gets a **personal AI agent** that has access to its own **cloud compute instance**
- Users interact via a **chat interface**; the agent can **execute tasks on its compute**
- The "koi" metaphor = a pet-like personalization of an AI + compute pair
- Next.js frontend (visible from `/_next/image` CDN paths)
- Invite-only early access with device-level auth persistence

I reverse-engineered the compute model from the task description ("each agent is backed by a cloud compute instance, e.g. EC2") and the general pattern of "AI agent with shell access" that has emerged as a category in 2025–2026.

---

## 2. AXON — Brand & Identity

Deliberately distinct from SkyKoi in every dimension:

| SkyKoi | AXON |
|---|---|
| Aquatic theme, koi fish, soft palette | Dark engineering aesthetic, electric cyan |
| "Koi with its own computer" (playful) | "Your agent. Your cloud." (direct, technical) |
| Invite code / device auth | Standard JWT/bcrypt signup, no invite gates |
| Nature imagery | Terminal UI, grid patterns, monospace |
| Soft blues and organic shapes | `#08080f` background, `#00d4ff` cyan, hard edges |

Name choice: **AXON** — a neural pathway that carries signal. Fits: agents carry intent → compute → output. Also: concise, all-caps readable, not taken in this exact form.

---

## 3. Architecture

```
User (browser)
    │
    ├─── HTTPS ──► GitHub Pages (Next.js static export)
    │               app/(auth)/login     → signup/login forms
    │               app/dashboard        → agent management
    │               app/agent/[id]       → chat + terminal UI
    │
    └─── WebSocket ──► EC2 t2.micro / Render.com
                        FastAPI backend
                        ├─ /api/auth/*       JWT auth (bcrypt)
                        ├─ /api/agents/*     CRUD + start/stop
                        └─ /ws/agents/{id}   WebSocket per agent
                              │
                              ├─── Docker SDK ──► agent containers
                              │    (one per user, isolated)
                              │    OR subprocess fallback (no Docker)
                              │
                              └─── Anthropic API ──► Claude agentic loop
                                   token streaming → command extraction
                                   → docker exec → output → next turn
```

### Data flow for a single agent turn
1. User types "clone this repo and run its tests"
2. Frontend sends `{type: "message", content: "..."}` over WebSocket
3. Backend builds message history (last 20 from DynamoDB/in-memory)
4. `ai_service.run_agent_turn()` opens a streaming Claude session
5. Tokens stream back → frontend shows them in real-time
6. Claude wraps commands in `<cmd>bash...</cmd>` tags
7. Backend detects tags → calls `docker exec` (or subprocess) in agent container
8. stdout/stderr stream back to client as `{type: "output", data: "..."}`
9. Output fed back into Claude context → next Claude token stream
10. Loop until Claude produces a pure-text response (no `<cmd>` tags)
11. `{type: "done"}` signals completion; history persisted to DynamoDB

---

## 4. Key Design Decisions

### 4.1 Docker containers, not separate EC2 instances
SkyKoi likely provisions one EC2 per user (implied by "its own computer"). On free tier, that's only 1 instance. My solution: **one EC2 t2.micro runs N Docker containers**, one per user agent. Each container:
- Has its own Linux filesystem (named volume, persistent)
- Is memory-limited (256 MB) and CPU-throttled (0.5 core)
- Has `cap_drop=ALL` security hardening
- Is on an internal Docker network (no external network access)

This maps cleanly to the "own computer" semantics at fraction of the cost.

**Scale path:** Replace with ECS Fargate tasks or separate t2.micro instances when revenue justifies it. The Docker API contract is identical.

### 4.2 Agent intelligence: `<cmd>` extraction, not tool-calling
Claude's native tool-calling is more structured but adds API complexity and latency. I chose a simpler loop: Claude wraps commands in `<cmd>...</cmd>` XML tags inline in its response. Benefits:
- Zero framework lock-in — works with any streaming Claude model
- Commands appear in the response stream naturally, not as separate API events
- Easier to debug: the agent's reasoning and its commands are in the same stream
- Iterations can be added/removed without changing the API schema

The tradeoff: slightly less structured than tool-calling, so command extraction could theoretically fail on malformed output. In practice, Claude is reliable about tag formatting when the system prompt is explicit.

### 4.3 Dual-mode backend: DynamoDB + in-memory fallback
The backend auto-detects whether AWS credentials exist:
- **With credentials:** real DynamoDB (production path)
- **Without credentials:** thread-safe in-memory dict store

This means the backend runs with zero AWS dependencies for local dev and on non-AWS platforms (Render.com free tier). The in-memory store is real data — not mocks — so all features work identically.

### 4.4 Dual-mode agent execution: Docker + subprocess fallback
Same pattern for the compute layer:
- **Docker available:** container per agent (proper isolation)
- **Docker unavailable:** `subprocess.run` in a per-agent temp directory

The subprocess mode is sufficient for demo/development. Production requires Docker. The `AGENT_MODE=subprocess` env var can force it.

### 4.5 JWT over Cognito for runtime auth
Cognito is provisioned in the CDK stack but the runtime auth uses bcrypt + JWT. Reasons:
- Cognito has SDKs that add ~200 KB to the bundle and complex client state
- JWT auth is portable — works on Render, Railway, EC2, or local with no config change
- Cognito is still available as a migration path (50K MAU free)

### 4.6 Static export + GitHub Pages for frontend
Next.js `output: 'export'` generates a fully static site that works on any CDN. GitHub Pages is free, automatic on push, and fast globally via GitHub's CDN. The SPA routing issue (GitHub Pages doesn't handle deep-links) is solved by the `404.html` pattern: the build copies `agent/new/index.html` to `404.html`, so GitHub Pages serves the SPA shell for any unknown path and client-side routing takes over.

In production, CloudFront with the CDK stack handles this with proper error responses.

---

## 5. AWS Free Tier Strategy

| Service | Role | Free limit |
|---|---|---|
| EC2 t2.micro | Backend API + Docker host | 750 hrs/mo |
| DynamoDB | Users, agents, messages | 25 GB + 25 WCU/RCU |
| S3 | Frontend static assets | 5 GB + 20K GET |
| CloudFront | CDN for frontend | 1 TB/mo transfer |
| Cognito | User pool (optional) | 50K MAU |
| Data transfer | API responses | 100 GB/mo |

The EC2 t2.micro is the only resource with a hard monthly limit (750 hours = one instance running 24/7). Everything else is usage-based and effectively free at low traffic.

**Cost risk:** DynamoDB Pay-Per-Request means no minimum charge but unbounded max. Mitigation: rate-limit API endpoints (easy to add to FastAPI middleware).

---

## 6. Tools & Services Used

| Layer | Tool | Why |
|---|---|---|
| Frontend | Next.js 14 App Router | Best-in-class SSR/SSG, server components |
| Styling | TailwindCSS 3 | Utility-first, excellent dark mode |
| Icons | Lucide React | Clean, consistent SVG icons |
| Backend | FastAPI + uvicorn | Python async, WebSocket support, auto-docs |
| Auth | python-jose + passlib | Standard JWT/bcrypt, no external deps |
| AI | Anthropic Python SDK | Claude 3.5 Haiku (fast, cheap, capable) |
| Agent compute | Docker SDK for Python | Container lifecycle via Unix socket |
| Database | boto3 DynamoDB | Free tier, serverless, AWS-native |
| IaC | AWS CDK Python | Type-safe, reproducible infra |
| CI/CD | GitHub Actions | Free, tight GitHub integration |
| Hosting (FE) | GitHub Pages | Free, auto-deploy, global CDN |
| Hosting (BE) | Render.com / EC2 | Free tier, Docker support |

---

## 7. Challenges & How I Solved Them

### Challenge 1: Static export + dynamic routes
**Problem:** Next.js `output: 'export'` errors on dynamic routes without `generateStaticParams`. An empty array still fails — at least one entry must be returned.
**Solution:** Return `[{id: "new"}]` as a shell entry. GitHub Actions then copies `out/agent/new/index.html` → `out/404.html`. GitHub Pages serves `404.html` for unknown paths, and React's client-side router reads the real ID from the URL. Clean SPA behavior.

### Challenge 2: `"use client"` + `generateStaticParams` can't coexist
**Problem:** `generateStaticParams` is a server-only export; `"use client"` prevents it from being in the same file.
**Solution:** Server/client split — `app/agent/[id]/page.tsx` is a thin server wrapper with `generateStaticParams`, and `components/AgentPageClient.tsx` holds all the client logic with `"use client"`.

### Challenge 3: AWS CLI not installed, Docker daemon not running
**Problem:** The deployment machine had Docker Desktop installed but daemon not running, and AWS CLI had broken dependencies (urllib3 version conflict in the conda environment).
**Solution:** Deployed frontend to GitHub Pages via GitHub Actions (no local tooling needed). Added `render.yaml` for one-click Render.com backend deploy. Full AWS CDK stack is written and ready — requires AWS credentials and `cdk deploy`.

### Challenge 4: In-memory store thread safety
**Problem:** FastAPI runs async workers; concurrent requests to the in-memory store could corrupt data.
**Solution:** `threading.Lock()` on all write operations. Reads are safe on CPython due to GIL, but writes explicitly serialize.

---

## 8. What Was Straightforward vs. Difficult

**Straightforward:**
- FastAPI WebSocket implementation — clean async streaming API
- The Claude agentic loop — `<cmd>` tag extraction is ~30 lines and works reliably
- DynamoDB dual-mode (real vs. in-memory) — clear boundary made this easy
- Tailwind dark-mode styling — utility classes map directly to the design
- CDK stack structure — VPC, EC2, DynamoDB, Cognito are all well-documented constructs

**Difficult:**
- Next.js static export edge cases — 3 iterations to get `generateStaticParams` + GitHub Pages SPA routing working
- Docker Desktop not running on Windows made the local Docker approach unusable
- The broken conda environment's urllib3 conflict blocked the AWS CLI entirely
- Designing the agent execution loop so Docker and subprocess modes are truly transparent to callers above

---

## 9. Assumptions Made

1. **"Backed by an EC2 instance"** was interpreted as: agents need dedicated compute, not necessarily a literal separate EC2. Docker containers on one EC2 satisfy the compute isolation requirement at free-tier scale.

2. **Free tier = zero cost**. If AWS free tier runs out (e.g., >750 EC2 hours), I would stop the instance. No paid resources provisioned.

3. **Agent intelligence = LLM + shell**. The prompt description was explicit about this. I chose Claude (Anthropic SDK) over Bedrock for simplicity; swapping to Bedrock requires only changing the `ai_service.py` client.

4. **Auth = standard account-based**. SkyKoi uses invite codes + device auth. I used standard email/password because it's more universally useful and shows a complete auth flow.

5. **"Fully functional" = complete feature loop works end-to-end**. I interpreted this as: sign up → create agent → chat → agent executes commands → output streams back. Not every edge case handled.

---

## 10. Deviations & Improvements Over SkyKoi

| Aspect | Deviation / Improvement |
|---|---|
| **Auth** | Standard email/password instead of invite codes. More accessible, easier to test. |
| **Compute model** | Docker containers on shared EC2 instead of one EC2 per user. Free-tier sustainable. |
| **Chat UI** | Dual-tab (Chat + Terminal). Terminal view gives direct access to the raw command stream — more useful for technical users. |
| **Streaming** | Every AI token streams in real-time, including command output. No "thinking" spinner — you see exactly what the agent is doing. |
| **IaC** | Full CDK stack means the infrastructure is version-controlled and reproducible, not manually configured. |
| **Portability** | Backend runs without AWS (in-memory + subprocess) for local dev and non-AWS platforms. SkyKoi appears AWS-only. |
| **AI loop transparency** | Commands visible inline in chat (`$ git clone ...`). The agent's reasoning and its actions are unified in one stream. |
| **Agent suggestion chips** | Landing example prompts ("Write a Python hello world", "Check disk space") lower the barrier to first interaction. |
