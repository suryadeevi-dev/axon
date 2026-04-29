"""
Agent execution service — three modes, checked in order:

  EC2        — if EC2_ENABLED=true + required env vars set (AWS, SSM)
  DOCKER     — if Docker socket available (local dev)
  SUBPROCESS — fallback (Render free tier / demo)
"""

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from observability import (
    sandbox_provision_duration,
    command_executions,
    command_duration,
)

log = logging.getLogger(__name__)

# ── Mode detection ─────────────────────────────────────────────────────────────
_FORCE_SUBPROCESS = os.getenv("AGENT_MODE", "").lower() == "subprocess"

from services import ec2_service

_USE_EC2 = ec2_service.ec2_available() and not _FORCE_SUBPROCESS


def _docker_available() -> bool:
    if _FORCE_SUBPROCESS or _USE_EC2:
        return False
    try:
        import docker
        docker.from_env().ping()
        return True
    except Exception:
        return False


_USE_DOCKER = _docker_available()

if _USE_EC2:
    log.info("Agent mode: ec2 (AWS EC2 + SSM, region=%s)", os.getenv("AWS_REGION", "us-east-1"))
elif _USE_DOCKER:
    log.info("Agent mode: docker")
else:
    log.info("Agent mode: subprocess (demo)")


def _active_mode() -> str:
    if _USE_EC2:
        return "ec2"
    if _USE_DOCKER:
        return "docker"
    return "subprocess"


# ── Subprocess workspace ───────────────────────────────────────────────────────
_BASE_WORKDIR = Path(tempfile.gettempdir()) / "axon-agents"
_BASE_WORKDIR.mkdir(exist_ok=True)


def _agent_workdir(agent_id: str) -> Path:
    d = _BASE_WORKDIR / agent_id[:12]
    d.mkdir(exist_ok=True)
    return d


# ── Docker helpers ─────────────────────────────────────────────────────────────
if _USE_DOCKER:
    import docker as _docker_mod

    AGENT_IMAGE  = os.getenv("AGENT_IMAGE", "axon-agent-base:latest")
    NETWORK_NAME = os.getenv("AGENT_NETWORK", "axon-agents")
    MEM_LIMIT    = os.getenv("AGENT_MEM_LIMIT", "256m")
    CPU_PERIOD   = 100_000
    CPU_QUOTA    = int(os.getenv("AGENT_CPU_QUOTA", "50000"))

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

def provision(agent_id: str, existing_container_id: Optional[str] = None) -> str:
    mode = _active_mode()
    t0 = time.monotonic()

    if _USE_EC2:
        result = ec2_service.provision(agent_id, existing_container_id)
        sandbox_provision_duration.labels(mode=mode).observe(time.monotonic() - t0)
        return result

    if _USE_DOCKER:
        _ensure_network()
        client = _client()
        name = _container_name(agent_id)
        try:
            client.containers.get(name).remove(force=True)
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
        sandbox_provision_duration.labels(mode=mode).observe(time.monotonic() - t0)
        return container.id

    workdir = _agent_workdir(agent_id)
    log.info("Subprocess agent provisioned at %s", workdir)
    sandbox_provision_duration.labels(mode=mode).observe(time.monotonic() - t0)
    return f"subprocess:{agent_id[:12]}"


def start(agent_id: str, container_id: Optional[str] = None) -> Optional[str]:
    if _USE_EC2:
        if container_id:
            return ec2_service.start(container_id)
        return provision(agent_id)
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
    return f"subprocess:{agent_id[:12]}"


def stop(agent_id: str, container_id: Optional[str] = None):
    if _USE_EC2:
        if container_id:
            ec2_service.stop(container_id)
        return
    if _USE_DOCKER:
        client = _client()
        try:
            client.containers.get(_container_name(agent_id)).stop(timeout=5)
        except _docker_mod.errors.NotFound:
            pass


def remove(agent_id: str, container_id: Optional[str] = None):
    if _USE_EC2:
        if container_id:
            ec2_service.terminate(container_id)
        return
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


def exec_command(
    agent_id: str,
    command: str,
    timeout: int = 30,
    container_id: Optional[str] = None,
) -> tuple[int, str]:
    mode = _active_mode()
    t0 = time.monotonic()
    exit_code, output = _exec_raw(agent_id, command, timeout, container_id)
    elapsed = time.monotonic() - t0

    status = "success" if exit_code == 0 else ("timeout" if "timed out" in output else "error")
    command_executions.labels(mode=mode, status=status).inc()
    command_duration.labels(mode=mode).observe(elapsed)
    return exit_code, output


def _exec_raw(
    agent_id: str,
    command: str,
    timeout: int,
    container_id: Optional[str],
) -> tuple[int, str]:
    if _USE_EC2:
        return ec2_service.exec_command(container_id or agent_id, command, timeout)

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


def status(agent_id: str, container_id: Optional[str] = None) -> str:
    if _USE_EC2:
        return ec2_service.status(container_id) if container_id else "stopped"
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
    workdir = _BASE_WORKDIR / agent_id[:12]
    return "running" if workdir.exists() else "stopped"
