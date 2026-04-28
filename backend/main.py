import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api import auth, agents, ws

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,https://axon.yourdomain.com",
).split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger(__name__).info("AXON backend starting up")
    yield
    logging.getLogger(__name__).info("AXON backend shutting down")


app = FastAPI(
    title="AXON API",
    version="0.1.0",
    description="AXON — autonomous agent platform",
    lifespan=lifespan,
)

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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "axon-api"}


@app.get("/")
async def root():
    return {"service": "AXON API", "version": "0.1.0"}
