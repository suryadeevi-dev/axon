# AXON — Your Agent. Your Cloud.

Autonomous AI agents with dedicated AWS compute. Chat with your agent in plain language — it writes code, runs commands, and gets real work done inside its own isolated EC2 instance.

**Live:** [suryadeevi-dev.github.io/axon](https://suryadeevi-dev.github.io/axon) · **API:** [axon-api-lhjm.onrender.com](https://axon-api-lhjm.onrender.com)

---

## What it does

- **Agent chat** — talk to your agent in natural language; it reasons, runs commands via SSM, and streams results in real time
- **Dedicated EC2 compute** — every agent runs in its own EC2 instance (Ubuntu 22.04, t3.micro) with a persistent EBS workspace
- **Google SSO + email auth** — sign in with Google or create an account with email/password
- **Persistent history** — conversations and agent state stored in DynamoDB
- **S3 file storage** — agent workspace files accessible at `/api/agents/{id}/files`
- **Observability** — Prometheus metrics at `/metrics`, structured JSON logs, per-request ID tracing

---

## Architecture

```
  Browser (GitHub Pages)
    │
    ├─ HTTPS → Render (FastAPI)
    │           ├─ /api/auth/*          JWT + Google OAuth 2.0
    │           ├─ /api/agents/*        agent CRUD + start/stop + files
    │           ├─ /ws/agents/{id}      chat WebSocket (AI + SSM command loop)
    │           └─ /metrics             Prometheus metrics
    │
    ├─ DynamoDB (AWS us-east-1)         users / agents / messages
    │
    ├─ EC2 (AWS us-east-1a)
    │   └─ per-agent Ubuntu 22.04 instance
    │        ├─ SSM Run Command ← backend executes shell commands
    │        └─ EBS gp3 8 GB   ← persistent /home/axon/workspace
    │
    └─ S3 (AWS)                         agent file artifacts (30-day lifecycle)
```

### Compute priority (auto-detected at startup)
```
EC2_ENABLED=true + EC2 env vars set  →  EC2  (production)
Docker socket available               →  Docker (local dev)
Neither                               →  subprocess (demo)
```

### AWS networking
```
VPC 10.0.0.0/16
  └─ Public subnet 10.0.1.0/24
       Security group: no inbound rules
       (SSM agent connects outbound HTTPS — no open ports required)
```

---

## Free-tier breakdown

| Service         | Usage                              | Free tier                       |
|-----------------|------------------------------------|---------------------------------|
| GitHub Pages    | Frontend (Next.js static)          | Unlimited                       |
| Render          | Backend (FastAPI)                  | 750 hrs/month                   |
| EC2 t3.micro    | Agent instances                    | 750 hrs/month (first 12 months) |
| EBS gp3         | Agent workspace (8 GB/agent)       | 30 GB total (first 12 months)   |
| S3              | Agent file artifacts               | 5 GB + 20K requests/month       |
| DynamoDB        | users, agents, messages            | 25 GB + 25 WCU/RCU (permanent)  |
| Groq 70B        | Llama 3.3 70B (primary AI)         | 100K tokens/day                 |
| Groq 8B         | Llama 3.1 8B (rate-limit fallback) | 500K tokens/day                 |
| Google OAuth    | SSO                                | Unlimited                       |
| GitHub Actions  | CI/CD                              | 2000 min/month                  |

---

## Observability

The backend exposes `/metrics` (Prometheus format). All logs are structured JSON with request-ID correlation.

### Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_requests_total` | Counter | `method`, `status_code`, `handler` | All HTTP requests (auto) |
| `http_request_duration_seconds` | Histogram | `method`, `handler` | HTTP latency (auto) |
| `axon_ws_connections_active` | Gauge | `ws_type` | Live WebSocket connections |
| `axon_agent_operations_total` | Counter | `operation` | create / start / stop / delete |
| `axon_ai_tokens_total` | Counter | `model` | Tokens generated per model |
| `axon_ai_rate_limit_fallbacks_total` | Counter | — | Groq rate-limit fallback events |
| `axon_ai_turn_seconds` | Histogram | — | Agent turn end-to-end latency |
| `axon_sandbox_provision_seconds` | Histogram | `mode` | EC2 / Docker provision latency |
| `axon_command_executions_total` | Counter | `mode`, `status` | SSM command success / error / timeout |
| `axon_command_execution_seconds` | Histogram | `mode` | SSM command latency |

### Log format

```json
{"ts":"2026-04-29T10:00:00","level":"INFO","logger":"api.ws","msg":"WS connected for agent abc user xyz","request_id":"a1b2c3d4"}
```

Every request gets an `X-Request-ID` (client-supplied or auto-generated) echoed in the response header and included in all log lines for that request.

**Scraping:** Grafana Cloud free tier (10K series) can scrape `https://axon-api-lhjm.onrender.com/metrics` directly as a Prometheus data source.

---

## Local Development

**Prerequisites:** Python 3.11+, Node 20+, Terraform 1.7+

```bash
git clone https://github.com/suryadeevi-dev/axon
cd axon
make setup

# Minimum .env: JWT_SECRET, GROQ_API_KEY
# AWS creds optional — falls back to in-memory store without them
# EC2_ENABLED=false by default — uses subprocess mode locally

make backend   # → http://localhost:8000
make frontend  # → http://localhost:3000
```

---

## AWS Infrastructure

All AWS resources are managed in `infra/` (Terraform). Run once before enabling EC2 mode.

```bash
cd infra
aws configure          # needs EC2 + IAM + S3 + SSM permissions
terraform init
terraform plan
terraform apply

# Copy these outputs into Render environment variables:
terraform output public_subnet_id              # → EC2_SUBNET_ID
terraform output agent_security_group_id       # → EC2_SG_ID
terraform output ubuntu_22_ami_id              # → EC2_AMI_ID
terraform output s3_bucket_name                # → EC2_S3_BUCKET
terraform output -raw backend_access_key_id    # → AWS_ACCESS_KEY_ID
terraform output -raw backend_secret_access_key # → AWS_SECRET_ACCESS_KEY
```

Set `EC2_ENABLED=true` in Render. The backend detects EC2 mode at startup and logs `Agent mode: ec2`.

---

## Production Deployment

### Backend (Render)
1. Connect repo → New Web Service → root dir `backend`
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1`
4. Add env vars from `render.yaml` (all documented with sources)

### Frontend (GitHub Pages)
Auto-deployed via `.github/workflows/deploy-frontend.yml` on every push to `master`.

### DynamoDB tables (one-time)
```bash
python scripts/create_dynamo_tables.py
```

---

## Project Structure

```
axon/
├── frontend/                    # Next.js 14 (static export → GitHub Pages)
│   ├── app/
│   │   ├── page.tsx             # Landing page
│   │   ├── (auth)/              # login / signup / OAuth callback
│   │   ├── dashboard/           # agent list
│   │   └── agent/[id]/          # chat + resources
│   ├── components/
│   │   ├── AgentPageClient.tsx  # main agent UI
│   │   ├── ResourcesPanel.tsx   # instance + model specs
│   │   └── Navbar.tsx
│   └── lib/
│       ├── api.ts               # Axios REST client
│       ├── auth.ts              # JWT + cookie helpers
│       └── ws.ts                # WebSocket client (auto-reconnect)
│
├── backend/                     # FastAPI (Python 3.11) → Render
│   ├── main.py                  # entrypoint, CORS, observability wiring
│   ├── observability.py         # Prometheus metrics, JSON logging, request-ID middleware
│   ├── api/
│   │   ├── auth.py              # signup, login, Google OAuth
│   │   ├── agents.py            # agent CRUD, start/stop, S3 files
│   │   └── ws.py                # chat WebSocket
│   ├── services/
│   │   ├── ai_service.py        # Groq agent loop + rate-limit fallback
│   │   ├── ec2_service.py       # EC2 provision/stop/terminate, SSM exec, S3
│   │   └── docker_service.py    # compute routing (EC2 → Docker → subprocess)
│   └── db/
│       └── dynamo.py            # DynamoDB + in-memory fallback
│
├── infra/                       # Terraform — AWS compute + networking + storage
│   ├── main.tf                  # provider, Ubuntu 22.04 AMI data source
│   ├── variables.tf
│   ├── outputs.tf               # values to copy into Render env vars
│   ├── vpc.tf                   # VPC, subnet, IGW, route table
│   ├── security.tf              # agent SG (egress-only)
│   ├── iam.tf                   # EC2 instance profile + backend IAM user
│   ├── s3.tf                    # agent file bucket
│   └── userdata.sh              # EC2 bootstrap script
│
├── scripts/
│   ├── create_dynamo_tables.py
│   └── iam_dynamo_policy.json
│
├── Makefile
├── render.yaml                  # Render config (all env vars documented)
└── DESIGN.md
```

---

## Environment Variables

### Backend (Render)
| Variable                | Description                                             | Required    |
|-------------------------|---------------------------------------------------------|-------------|
| `JWT_SECRET`            | JWT signing secret (auto-generated by Render)           | Yes         |
| `GROQ_API_KEY`          | Groq API key (free at console.groq.com)                 | Yes         |
| `AWS_ACCESS_KEY_ID`     | `terraform output -raw backend_access_key_id`           | Yes         |
| `AWS_SECRET_ACCESS_KEY` | `terraform output -raw backend_secret_access_key`       | Yes         |
| `AWS_REGION`            | AWS region                                              | `us-east-1` |
| `EC2_ENABLED`           | `true` to activate EC2 mode                             | Yes         |
| `EC2_AMI_ID`            | `terraform output ubuntu_22_ami_id`                     | Yes         |
| `EC2_SUBNET_ID`         | `terraform output public_subnet_id`                     | Yes         |
| `EC2_SG_ID`             | `terraform output agent_security_group_id`              | Yes         |
| `EC2_INSTANCE_PROFILE`  | Instance profile name                                   | `axon-agent-instance-profile` |
| `EC2_INSTANCE_TYPE`     | Instance type                                           | `t3.micro`  |
| `EC2_S3_BUCKET`         | `terraform output s3_bucket_name`                       | Yes         |
| `GOOGLE_CLIENT_ID`      | Google OAuth client ID                                  | Yes         |
| `GOOGLE_CLIENT_SECRET`  | Google OAuth client secret                              | Yes         |
| `GOOGLE_REDIRECT_URI`   | `https://<render-url>/api/auth/google/callback`         | Yes         |
| `FRONTEND_URL`          | `https://suryadeevi-dev.github.io/axon`                 | Yes         |
| `CORS_ORIGINS`          | Comma-separated allowed origins                         | Yes         |

### Frontend (build-time)
| Variable              | Description             | Default                 |
|-----------------------|-------------------------|-------------------------|
| `NEXT_PUBLIC_API_URL` | Backend REST URL        | `http://localhost:8000` |
| `NEXT_PUBLIC_WS_URL`  | Backend WebSocket URL   | `ws://localhost:8000`   |
