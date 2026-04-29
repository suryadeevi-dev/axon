"""
Observability layer for AXON.

Provides:
  - JSON structured logging with request-ID correlation
  - Prometheus custom metrics (WS connections, agent ops, AI tokens,
    sandbox provision latency, command execution latency)
  - RequestIDMiddleware that injects X-Request-ID on every request

HTTP request metrics (count + duration histograms by method/handler/status)
are added automatically by prometheus_fastapi_instrumentator in main.py.

Usage in main.py:
    from observability import setup_logging, setup_metrics, RequestIDMiddleware
    setup_logging()
    app.add_middleware(RequestIDMiddleware)
    setup_metrics(app)       # mounts /metrics
"""

import json
import logging
import uuid
from contextvars import ContextVar

from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# ── Request correlation ────────────────────────────────────────────────────────

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


# ── Structured JSON logging ────────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts":         self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":      record.levelname,
            "logger":     record.name,
            "msg":        record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging():
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # Suppress chatty third-party loggers
    for name in ("uvicorn.access", "botocore", "boto3", "s3transfer"):
        logging.getLogger(name).setLevel(logging.WARNING)


# ── Request-ID middleware ──────────────────────────────────────────────────────

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_var.set(req_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = req_id
        return response


# ── Custom metrics ─────────────────────────────────────────────────────────────

# Active WebSocket connections
ws_connections = Gauge(
    "axon_ws_connections_active",
    "Active WebSocket connections",
    ["ws_type"],   # chat | pty
)

# Agent lifecycle operations
agent_ops = Counter(
    "axon_agent_operations_total",
    "Agent lifecycle operations",
    ["operation"],  # create | start | stop | delete
)

# AI tokens streamed per model
ai_tokens = Counter(
    "axon_ai_tokens_total",
    "AI tokens generated",
    ["model"],
)

# Rate-limit fallback to smaller model
ai_fallbacks = Counter(
    "axon_ai_rate_limit_fallbacks_total",
    "Times AI fell back to smaller model due to rate limit",
)

# Duration of a complete agent turn (first token → done event)
ai_turn_duration = Histogram(
    "axon_ai_turn_seconds",
    "Duration of one complete agent turn",
    buckets=[0.5, 1, 2, 5, 10, 30, 60],
)

# Sandbox provision latency per compute mode
sandbox_provision_duration = Histogram(
    "axon_sandbox_provision_seconds",
    "Time to provision a compute sandbox",
    ["mode"],   # ec2 | docker | subprocess
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300],
)

# Command execution count and latency per compute mode
command_executions = Counter(
    "axon_command_executions_total",
    "Sandbox command executions",
    ["mode", "status"],   # status: success | error | timeout
)

command_duration = Histogram(
    "axon_command_execution_seconds",
    "Sandbox command execution duration",
    ["mode"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
)


# ── Wire-up helper ─────────────────────────────────────────────────────────────

def setup_metrics(app):
    """Instrument the FastAPI app and expose /metrics."""
    Instrumentator(
        should_group_status_codes=False,
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
