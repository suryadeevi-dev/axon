"""
Manages per-agent Docker containers on the host machine.
Each agent gets an isolated container with a persistent work volume.
"""

import docker
import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

AGENT_IMAGE = os.getenv("AGENT_IMAGE", "axon-agent-base:latest")
NETWORK_NAME = os.getenv("AGENT_NETWORK", "axon-agents")
MEM_LIMIT = os.getenv("AGENT_MEM_LIMIT", "256m")
CPU_PERIOD = 100_000
CPU_QUOTA = int(os.getenv("AGENT_CPU_QUOTA", "50000"))  # 0.5 CPU
WORK_DIR = "/home/axon/workspace"


def _client() -> docker.DockerClient:
    return docker.from_env()


def _container_name(agent_id: str) -> str:
    return f"axon-agent-{agent_id[:12]}"


def _ensure_network():
    client = _client()
    try:
        client.networks.get(NETWORK_NAME)
    except docker.errors.NotFound:
        client.networks.create(
            NETWORK_NAME,
            driver="bridge",
            internal=True,
        )


def provision(agent_id: str) -> str:
    """Start a container for the agent. Returns container ID."""
    _ensure_network()
    client = _client()
    name = _container_name(agent_id)

    # Remove any stale container with same name
    try:
        old = client.containers.get(name)
        old.remove(force=True)
    except docker.errors.NotFound:
        pass

    container = client.containers.run(
        AGENT_IMAGE,
        name=name,
        detach=True,
        network=NETWORK_NAME,
        mem_limit=MEM_LIMIT,
        cpu_period=CPU_PERIOD,
        cpu_quota=CPU_QUOTA,
        # No port bindings — access via exec only
        environment={
            "AGENT_ID": agent_id,
            "HOME": "/home/axon",
        },
        working_dir=WORK_DIR,
        # Security hardening
        cap_drop=["ALL"],
        cap_add=["CHOWN", "SETUID", "SETGID"],
        security_opt=["no-new-privileges"],
        read_only=False,
        volumes={
            f"axon-vol-{agent_id[:12]}": {"bind": WORK_DIR, "mode": "rw"},
        },
        restart_policy={"Name": "unless-stopped"},
    )
    log.info("Provisioned container %s for agent %s", container.id[:12], agent_id)
    return container.id


def stop(agent_id: str):
    """Stop (but don't remove) the agent container."""
    client = _client()
    name = _container_name(agent_id)
    try:
        container = client.containers.get(name)
        container.stop(timeout=5)
        log.info("Stopped container for agent %s", agent_id)
    except docker.errors.NotFound:
        log.warning("Container not found for agent %s", agent_id)


def start(agent_id: str) -> Optional[str]:
    """Start a stopped container. Returns container ID or None."""
    client = _client()
    name = _container_name(agent_id)
    try:
        container = client.containers.get(name)
        if container.status != "running":
            container.start()
        log.info("Started container for agent %s", agent_id)
        return container.id
    except docker.errors.NotFound:
        # Container gone — reprovision
        return provision(agent_id)


def remove(agent_id: str):
    """Stop and remove container + volume."""
    client = _client()
    name = _container_name(agent_id)
    try:
        container = client.containers.get(name)
        container.remove(force=True)
        log.info("Removed container for agent %s", agent_id)
    except docker.errors.NotFound:
        pass
    try:
        vol = client.volumes.get(f"axon-vol-{agent_id[:12]}")
        vol.remove()
    except docker.errors.NotFound:
        pass


def exec_command(agent_id: str, command: str, timeout: int = 30) -> tuple[int, str]:
    """
    Execute a shell command in the agent container.
    Returns (exit_code, output).
    """
    client = _client()
    name = _container_name(agent_id)
    try:
        container = client.containers.get(name)
        result = container.exec_run(
            cmd=["bash", "-c", command],
            workdir=WORK_DIR,
            demux=False,
            tty=False,
            environment={"TERM": "xterm-256color"},
        )
        output = result.output.decode("utf-8", errors="replace") if result.output else ""
        return result.exit_code or 0, output
    except docker.errors.NotFound:
        return 1, f"Container not found for agent {agent_id}"
    except Exception as e:
        return 1, str(e)


def status(agent_id: str) -> str:
    """Returns 'running', 'stopped', or 'error'."""
    client = _client()
    name = _container_name(agent_id)
    try:
        container = client.containers.get(name)
        if container.status == "running":
            return "running"
        return "stopped"
    except docker.errors.NotFound:
        return "stopped"
    except Exception:
        return "error"
