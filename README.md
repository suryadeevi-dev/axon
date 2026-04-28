# AXON — Your Agent. Your Cloud.

Autonomous AI agents with dedicated cloud compute. Chat with your agent in plain language — it writes code, runs commands, and gets real work done on its own Linux environment.

**Brand:** Completely original — dark engineering aesthetic, electric cyan + deep charcoal, no relation to SkyKoi.

---

## Architecture

```
                   ┌─────────────────────────────────────────────────────┐
                   │                  AWS (Free Tier)                    │
                   │                                                     │
  User ──HTTPS──►  │  CloudFront  ──►  S3 (Next.js static)              │
                   │                                                     │
  User ──WS──────► │  EC2 t2.micro                                       │
                   │  ├─ FastAPI backend (uvicorn)                       │
                   │  ├─ Docker daemon                                   │
                   │  │   ├─ axon-agent-{id} (container per user)       │
                   │  │   └─ axon-agent-{id} ...                        │
                   │  └─ DynamoDB (users, agents, messages)              │
                   │                                                     │
                   │  Cognito (auth, 50K MAU free)                      │
                   └─────────────────────────────────────────────────────┘
```

### Free-tier breakdown
| Service        | Usage           | Free Tier                  |
|----------------|-----------------|----------------------------|
| EC2 t2.micro   | 1 instance      | 750 hrs/month              |
| DynamoDB       | 3 tables        | 25 GB + 25 WCU/RCU         |
| S3             | Frontend assets | 5 GB + 20K GET             |
| CloudFront     | CDN             | 1 TB transfer/month        |
| Cognito        | Auth            | 50,000 MAU                 |
| Data transfer  | API responses   | 100 GB/month               |

---

## Local Development (5 minutes)

**Prerequisites:** Docker, Node 20+, Python 3.11+

```bash
# 1. Clone and configure
git clone https://github.com/suryadeevi-dev/axon
cd axon
cp .env.example .env
# Edit .env — set JWT_SECRET and ANTHROPIC_API_KEY

# 2. Build the agent Docker image
make build-agent

# 3. Start everything
make dev
# → API:      http://localhost:8000
# → Frontend: http://localhost:3000
# → Dynamo:   http://localhost:8001
```

### Manual start (no Docker Compose)

```bash
# Terminal 1 — DynamoDB Local
docker run -p 8001:8000 amazon/dynamodb-local -jar DynamoDBLocal.jar -sharedDb -inMemory

# Terminal 2 — Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DYNAMO_ENDPOINT_URL=http://localhost:8001 uvicorn main:app --reload --port 8000

# Terminal 3 — Frontend
cd frontend
npm install
npm run dev
```

---

## Production Deployment (AWS)

### Prerequisites
- AWS CLI configured (`aws configure`)
- AWS CDK installed (`npm install -g aws-cdk`)
- Docker running

### One-command deploy

```bash
export AWS_PROFILE=your-profile
export AWS_REGION=us-east-1

./scripts/deploy.sh
```

### Step-by-step

```bash
# 1. Bootstrap CDK (once per account/region)
make infra-bootstrap

# 2. Deploy infrastructure
make infra-deploy
# Outputs: EC2 IP, CloudFront URL, table names

# 3. Configure the EC2 instance
EC2_IP=$(aws cloudformation describe-stacks \
  --stack-name AxonStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiPublicIp`].OutputValue' \
  --output text)

# Copy environment file
scp .env ubuntu@$EC2_IP:~/axon/.env

# Restart the API service
ssh ubuntu@$EC2_IP "sudo systemctl restart axon-api && sudo systemctl status axon-api"

# 4. Deploy frontend
make deploy-frontend
```

---

## Project Structure

```
axon/
├── frontend/                  # Next.js 14 App Router
│   ├── app/
│   │   ├── page.tsx           # Landing page
│   │   ├── (auth)/login/      # Sign in
│   │   ├── (auth)/signup/     # Create account
│   │   ├── dashboard/         # Agents dashboard
│   │   └── agent/[id]/        # Agent chat + terminal
│   ├── components/
│   │   ├── Navbar.tsx
│   │   ├── AgentCard.tsx
│   │   └── AgentChat.tsx
│   └── lib/
│       ├── api.ts             # Axios client
│       ├── auth.ts            # JWT / cookie helpers
│       └── ws.ts              # WebSocket client
│
├── backend/                   # FastAPI
│   ├── main.py                # App entrypoint + CORS
│   ├── api/
│   │   ├── auth.py            # /api/auth/* (signup, login, me)
│   │   ├── agents.py          # /api/agents/* (CRUD + start/stop)
│   │   └── ws.py              # /ws/agents/{id} (WebSocket)
│   ├── services/
│   │   ├── docker_service.py  # Container lifecycle management
│   │   └── ai_service.py      # Claude agent loop (stream tokens + exec cmds)
│   ├── db/dynamo.py           # DynamoDB operations
│   └── models/                # Pydantic models
│
├── docker/
│   └── agent-base/            # Ubuntu 22.04 + Python + Node + common tools
│
├── infra/                     # AWS CDK (Python)
│   ├── app.py
│   └── stacks/axon_stack.py   # VPC, EC2, S3, CF, DynamoDB, Cognito, IAM
│
├── scripts/
│   └── deploy.sh              # Full production deploy
├── docker-compose.yml         # Local dev stack
├── Makefile                   # Common commands
└── .env.example               # Environment template
```

---

## Key Design Decisions

### Agent compute model
Each agent is a **Docker container on the EC2 host**, not a separate EC2 instance. This is the free-tier-compatible approach: one t2.micro hosts the API and N agent containers. For production scale, this maps cleanly to ECS per-task or separate EC2 per tier.

### Agent intelligence
The AI service (`backend/services/ai_service.py`) uses a simple agentic loop:
1. Claude generates a response that may include `<cmd>...</cmd>` tags
2. Commands are executed via `docker exec` in the agent's container
3. Output is fed back to Claude as context
4. Loop continues until Claude produces a pure text response (no commands)

This is intentionally simple and production-ready — no tool-calling framework lock-in.

### Auth
JWT-based (no Cognito dependency at runtime). The Cognito User Pool is provisioned but the default auth uses bcrypt+JWT directly, keeping the API portable. Swap to Cognito by implementing the cognito_service.

### WebSocket reconnect
The frontend WS client does exponential backoff with up to 5 reconnect attempts. Agent state is persisted in DynamoDB so context survives reconnects.

---

## Environment Variables

| Variable               | Description                                  | Default              |
|------------------------|----------------------------------------------|----------------------|
| `JWT_SECRET`           | JWT signing secret (required)                | —                    |
| `ANTHROPIC_API_KEY`    | Claude API key (required)                    | —                    |
| `AWS_REGION`           | AWS region                                   | `us-east-1`          |
| `DYNAMO_ENDPOINT_URL`  | Override for DynamoDB Local                  | AWS endpoint         |
| `AGENT_IMAGE`          | Docker image for agent containers            | `axon-agent-base`    |
| `AGENT_MEM_LIMIT`      | Per-container memory limit                   | `256m`               |
| `CORS_ORIGINS`         | Comma-separated allowed origins              | `http://localhost:3000` |

---

## Roadmap

- [ ] Custom domain + ACM certificate via CDK
- [ ] Agent file browser (list/download workspace files)
- [ ] Shared agent sessions (invite collaborators)
- [ ] Agent scheduling (cron jobs)
- [ ] Swap Claude API for Amazon Bedrock (native AWS)
- [ ] Auto-suspend idle agents (save EC2 resources)
- [ ] ECS Fargate migration path for multi-user scale
