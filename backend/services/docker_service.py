"""
Agent execution service — dual mode:

  DOCKER mode (default when Docker socket is available):
    Each agent = isolated Docker container with persistent volume.

  SUBPROCESS mode (fallback when Docker is unavailable):
    Each agent = sandboxed subprocess in a per-agent temp directory.
    Suitable for Render/Railway free tier and local dev without Docker.
    No container-level isolation — treat as a trusted demo environment.
"""

import logging
import os
import subprocess
import tempfile
import asyncio
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Mode detection ────────────────────────────────────────────────────────────
_DOCKER_SOCKET = "/var/run/docker.sock"
_FORCE_SUBPROCESS = os.getenv("AGENT_MODE", "").lower() == "subprocess"

def _docker_available() -> bool:
    if _FORCE_SUBPROCESS:
        return False
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False

_USE_DOCKER = _docker_available()
log.info("Agent mode: %s", "docker" if _USE_DOCKER else "subprocess")


# ── Shared workspace dir for subprocess mode ──────────────────────────────────
_BASE_WORKDIR = Path(tempfile.gettempdir()) / "axon-agents"
_BASE_WORKDIR.mkdir(exist_ok=True)


def _agent_workdir(agent_id: str) -> Path:
    d = _BASE_WORKDIR / agent_id[:12]
    d.mkdir(exist_ok=True)
    return d


# ── Docker helpers ─────────────────────────────────────────────────────────────
if _USE_DOCKER:
    import docker as _docker_mod

    AGENT_IMAGE = os.getenv("AGENT_IMAGE", "axon-agent-base:latest")
    NETWORK_NAME = os.getenv("AGENT_NETWORK", "axon-agents")
    MEM_LIMIT = os.getenv("AGENT_MEM_LIMIT", "256m")
    CPU_PERIOD = 100_000
    CPU_QUOTA = int(os.getenv("AGENT_CPU_QUOTA", "50000"))

    def _client():
        return _docker_mod.from_env()

    def _container_name(agent_id: str) -> str:
        return f"axon-agent-{agent_id[:12]}"

    def _ensure_network():
        client = _client()
        try:
            client.networks.get(NETWORK_NAME)
        except _docker_mod.errors.NotFound:
            client.networks.create(NETWORK_NAME, driver="bridge", internal=True)


# ── Public API ─────────────────────────────────────────────────────────────────

def provision(agent_id: str) -> str:
    if _USE_DOCKER:
        _ensure_network()
        client = _client()
        name = _container_name(agent_id)
        try:
            old = client.containers.get(name)
            old.remove(force=True)
        except _docker_mod.errors.NotFound:
            pass
        container = client.containers.run(
            AGENT_IMAGE, name=name, detach=True, network=NETWORK_NAME,
            mem_limit=MEM_LIMIT, cpu_period=CPU_PERIOD, cpu_quota=CPU_QUOTA,
            environment={"AGENT_ID": agent_id, "HOME": "/home/axon"},
            working_dir="/home/axon/workspace",
            cap_drop=["ALL"], cap_add=["CHOWN", "SETUID", "SETGID"],
            security_opt=["no-new-privileges"],
            volumes={f"axon-vol-{agent_id[:12]}": {"bind": "/home/axon/workspace", "mode": "rw"}},
            restart_policy={"Name": "unless-stopped"},
        )
        return container.id
    else:
        workdir = _agent_workdir(agent_id)
        log.info("Subprocess agent provisioned at %s", workdir)
        return f"subprocess:{agent_id[:12]}"


def start(agent_id: str) -> Optional[str]:
    if _USE_DOCKER:
        client = _client()
        name = _container_name(agent_id)
        try:
            container = client.containers.get(name)
            if container.status != "running":
                container.start()
            return container.id
        except _docker_mod.errors.NotFound:
            return provision(agent_id)
    else:
        workdir = _agent_workdir(agent_id)
        return f"subprocess:{agent_id[:12]}"


def stop(agent_id: str):
    if _USE_DOCKER:
        client = _client()
        try:
            client.containers.get(_container_name(agent_id)).stop(timeout=5)
        except _docker_mod.errors.NotFound:
            pass
    # subprocess mode: no-op (process exits after each command anyway)


def remove(agent_id: str):
    if _USE_DOCKER:
        client = _client()
        name = _container_name(agent_id)
        try:
            client.containers.get(name).remove(force=True)
        except _docker_mod.errors.NotFound:
            pass
        try:
            client.volumes.get(f"axon-vol-{agent_id[:12]}").remove()
        except _docker_mod.errors.NotFound:
            pass
    else:
        import shutil
        workdir = _agent_workdir(agent_id)
        if workdir.exists():
            shutil.rmtree(workdir, ignore_errors=True)


def exec_command(agent_id: str, command: str, timeout: int = 30) -> tuple[int, str]:
    if _USE_DOCKER:
        client = _client()
        name = _container_name(agent_id)
        try:
            container = client.containers.get(name)
            result = container.exec_run(
                cmd=["bash", "-c", command],
                workdir="/home/axon/workspace",
                demux=False, tty=False,
                environment={"TERM": "xterm-256color"},
            )
            output = result.output.decode("utf-8", errors="replace") if result.output else ""
            return result.exit_code or 0, output
        except _docker_mod.errors.NotFound:
            return 1, f"Container not found for agent {agent_id}"
        except Exception as e:
            return 1, str(e)
    else:
        workdir = _agent_workdir(agent_id)
        try:
            result = subprocess.run(
                ["bash", "-c", command],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "HOME": str(workdir), "TERM": "xterm-256color"},
            )
            output = result.stdout + (f"\n{result.stderr}" if result.stderr else "")
            return result.returncode, output.strip()
        except subprocess.TimeoutExpired:
            return 1, f"Command timed out after {timeout}s"
        except Exception as e:
            return 1, str(e)


def status(agent_id: str) -> str:
    if _USE_DOCKER:
        client = _client()
        name = _container_name(agent_id)
        try:
            container = client.containers.get(name)
            return "running" if container.status == "running" else "stopped"
        except _docker_mod.errors.NotFound:
            return "stopped"
        except Exception:
            return "error"
    else:
        # In subprocess mode, agents are always "running" once created
        workdir = _BASE_WORKDIR / agent_id[:12]
        return "running" if workdir.exists() else "stopped"
