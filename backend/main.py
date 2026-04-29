import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from observability import setup_logging, setup_metrics, RequestIDMiddleware

setup_logging()

from api import auth, agents, ws
from services.docker_service import _USE_EC2, _USE_DOCKER
from services.ec2_service import ec2_available
from db.dynamo import _USE_DYNAMO

ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,https://axon.yourdomain.com",
).split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    logging.getLogger(__name__).info("AXON backend starting up")
    yield
    logging.getLogger(__name__).info("AXON backend shutting down")


app = FastAPI(
    title="AXON API",
    version="0.1.0",
    description="AXON — autonomous agent platform",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(ws.router)

setup_metrics(app)


@app.get("/health")
async def health():
    return {
        "status":       "ok",
        "service":      "axon-api",
        "compute_mode": "ec2" if _USE_EC2 else ("docker" if _USE_DOCKER else "subprocess"),
        "db_mode":      "dynamodb" if _USE_DYNAMO else "in-memory",
        "ec2_enabled":  ec2_available(),
    }


@app.get("/")
async def root():
    return {"service": "AXON API", "version": "0.1.0"}
