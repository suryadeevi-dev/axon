# AXON — Your Agent. Your Cloud.

Autonomous AI agents with dedicated cloud compute. Chat with your agent in plain language — it writes code, runs commands, and gets real work done inside its own isolated Linux sandbox.

**Live:** [suryadeevi-dev.github.io/axon](https://suryadeevi-dev.github.io/axon) · **API:** [axon-api-lhjm.onrender.com](https://axon-api-lhjm.onrender.com)

---

## What it does

- **Agent chat** — talk to your agent in natural language; it reasons, runs commands, and streams results back in real time
- **Interactive terminal** — full xterm.js PTY connected directly to your agent's sandbox
- **Isolated sandboxes** — every agent runs in its own E2B cloud container (Ubuntu 22.04, 2 vCPU, 512 MB RAM)
- **Google SSO + email auth** — sign in with Google or create an account with email/password
- **Persistent history** — conversations and agent state stored in DynamoDB (survives backend restarts)
- **Light / dark mode** — toggle in the navbar

---

## Architecture

```
  Browser (GitHub Pages)
    │
    ├─ HTTPS → Render (FastAPI)
    │           ├─ /api/auth/*       JWT + Google OAuth 2.0
    │           ├─ /api/agents/*     agent CRUD + start/stop
    │           ├─ /ws/agents/{id}   chat WebSocket (AI + command loop)
    │           └─ /ws/agents/{id}/pty  PTY WebSocket (xterm.js ↔ E2B)
    │
    ├─ DynamoDB (AWS)               users / agents / messages
    │
    └─ E2B (e2b.dev)                isolated Linux sandboxes per agent
```

### Compute priority (auto-detected at startup)
```
E2B available (E2B_API_KEY set)  →  real isolated cloud sandbox
Docker available                  →  local Docker container
Neither                          →  subprocess (demo/fallback mode)
```

### Free-tier breakdown
| Service         | Usage                          | Free Tier                    |
|-----------------|--------------------------------|------------------------------|
| GitHub Pages    | Frontend (Next.js static)      | Unlimited                    |
| Render          | Backend (FastAPI + uvicorn)    | 750 hrs/month                |
| E2B             | Agent sandboxes                | 100 hrs/month                |
| DynamoDB        | users, agents, messages        | 25 GB + 25 WCU/RCU (always)  |
| Groq            | Llama 3.3 70B (primary AI)     | 100K tokens/day              |
| Groq            | Llama 3.1 8B (fallback AI)     | 500K tokens/day              |

---

## Local Development

**Prerequisites:** Python 3.11+, Node 20+

```bash
git clone https://github.com/suryadeevi-dev/axon
cd axon
cp .env .env.local   # fill in keys — see Environment Variables below

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

---

## Production Deployment

### Backend (Render)
1. Connect the repo to Render → New Web Service → root dir `backend`
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1`
4. Add environment variables (see below)

### Frontend (GitHub Pages)
Deployed automatically via `.github/workflows/deploy-frontend.yml` on every push to `master`.

### DynamoDB tables (one-time setup)
```bash
# With admin AWS credentials:
python scripts/create_dynamo_tables.py
```
Creates: `axon-users`, `axon-agents`, `axon-messages` with required GSIs.

---

## Project Structure

```
axon/
├── frontend/                    # Next.js 14 App Router (static export)
│   ├── app/
│   │   ├── page.tsx             # Landing page
│   │   ├── (auth)/login/        # Sign in
│   │   ├── (auth)/signup/       # Create account
│   │   ├── dashboard/           # Agent dashboard
│   │   └── agent/[id]/          # Agent chat + terminal + resources
│   ├── components/
│   │   ├── AgentPageClient.tsx  # Main agent page (chat / terminal / resources tabs)
│   │   ├── XTerminal.tsx        # xterm.js PTY component
│   │   ├── ResourcesPanel.tsx   # Sandbox + model specs display
│   │   ├── Navbar.tsx           # Nav + theme toggle
│   │   └── ThemeToggle.tsx      # Light/dark mode
│   └── lib/
│       ├── api.ts               # Axios REST client
│       ├── auth.ts              # JWT + cookie helpers
│       └── ws.ts                # WebSocket client (auto-reconnect)
│
├── backend/                     # FastAPI (Python 3.11)
│   ├── main.py                  # App entrypoint + CORS
│   ├── api/
│   │   ├── auth.py              # signup, login, Google OAuth callback
│   │   ├── agents.py            # agent CRUD, start/stop, files
│   │   └── ws.py                # chat WS + PTY WS endpoints
│   ├── services/
│   │   ├── ai_service.py        # Groq agent loop (stream tokens + exec cmds)
│   │   ├── e2b_service.py       # E2B sandbox lifecycle + PTY
│   │   └── docker_service.py    # Compute mode routing (E2B / Docker / subprocess)
│   └── db/
│       └── dynamo.py            # DynamoDB + in-memory fallback
│
├── scripts/
│   ├── create_dynamo_tables.py  # One-time DynamoDB table setup
│   └── iam_dynamo_policy.json   # Least-privilege IAM policy template
│
└── render.yaml                  # Render deployment config
```

---

## Environment Variables

### Backend (Render)
| Variable                | Description                                      | Required |
|-------------------------|--------------------------------------------------|----------|
| `JWT_SECRET`            | JWT signing secret (32+ chars)                   | Yes      |
| `GROQ_API_KEY`          | Groq API key (free at console.groq.com)          | Yes      |
| `E2B_API_KEY`           | E2B API key (free at e2b.dev)                    | Yes      |
| `AWS_ACCESS_KEY_ID`     | IAM user key (least-privilege DynamoDB only)     | Yes      |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret                                  | Yes      |
| `AWS_REGION`            | DynamoDB region                                  | `us-east-1` |
| `GOOGLE_CLIENT_ID`      | Google OAuth client ID                           | Yes      |
| `GOOGLE_CLIENT_SECRET`  | Google OAuth client secret                       | Yes      |
| `GOOGLE_REDIRECT_URI`   | `https://<render-url>/api/auth/google/callback`  | Yes      |
| `FRONTEND_URL`          | `https://suryadeevi-dev.github.io/axon`          | Yes      |
| `CORS_ORIGINS`          | Comma-separated allowed origins                  | Yes      |

### Frontend (GitHub Pages / build)
| Variable                | Description               | Default               |
|-------------------------|---------------------------|-----------------------|
| `NEXT_PUBLIC_API_URL`   | Backend REST URL          | `http://localhost:8000` |
| `NEXT_PUBLIC_WS_URL`    | Backend WebSocket URL     | `ws://localhost:8000`   |
