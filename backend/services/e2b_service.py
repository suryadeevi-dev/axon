"""
E2B sandbox service — real isolated Linux containers, free tier.

Each agent maps to one persistent E2B sandbox.
sandbox_id is stored in DynamoDB/memory as container_id.

Modes available (checked in order):
  1. E2B  — if E2B_API_KEY is set
  2. Docker — if Docker socket is available
  3. Subprocess — fallback (Render free tier)
"""

import asyncio
import logging
import os
from typing import Optional, Callable

log = logging.getLogger(__name__)

E2B_API_KEY = os.getenv("E2B_API_KEY", "")
SANDBOX_TIMEOUT = int(os.getenv("E2B_SANDBOX_TIMEOUT", "3600"))  # 1 hour

# Active PTY sessions: agent_id → terminal object
_pty_sessions: dict[str, object] = {}


def e2b_available() -> bool:
    return bool(E2B_API_KEY)


def _connect_sandbox(sandbox_id: str):
    """Reconnect to an existing sandbox. Raises if sandbox is gone."""
    from e2b import Sandbox
    # e2b 1.x uses Sandbox.connect(); 0.x used Sandbox.reconnect()
    connect_fn = getattr(Sandbox, "connect", None) or getattr(Sandbox, "reconnect", None)
    if connect_fn is None:
        raise RuntimeError("e2b SDK missing connect/reconnect method")
    sbx = connect_fn(sandbox_id, api_key=E2B_API_KEY, timeout=SANDBOX_TIMEOUT)
    return sbx


def _new_sandbox():
    """Spin up a fresh E2B sandbox."""
    from e2b import Sandbox
    sbx = Sandbox(api_key=E2B_API_KEY, timeout=SANDBOX_TIMEOUT)
    log.info("E2B sandbox created: %s", sbx.sandbox_id)
    return sbx


def _get_sandbox(sandbox_id: Optional[str] = None) -> tuple[object, str]:
    """
    Returns (sandbox, actual_sandbox_id).
    If sandbox_id is provided, reconnects. Falls back to new sandbox on expiry.
    Callers must persist the returned sandbox_id if it differs from the input.
    """
    if sandbox_id:
        try:
            sbx = _connect_sandbox(sandbox_id)
            return sbx, sandbox_id
        except Exception:
            log.info("E2B sandbox %s expired or unreachable, provisioning new one", sandbox_id)
    sbx = _new_sandbox()
    return sbx, sbx.sandbox_id


def provision(sandbox_id: Optional[str] = None) -> str:
    """Create or reconnect an E2B sandbox. Returns the (possibly new) sandbox_id."""
    sbx, actual_id = _get_sandbox(sandbox_id)
    try:
        sbx.commands.run("mkdir -p /home/user/workspace", timeout=10)
    except Exception:
        pass
    return actual_id


def exec_command(sandbox_id: str, command: str, timeout: int = 30) -> tuple[int, str]:
    """Run a command in the sandbox, return (exit_code, output)."""
    try:
        sbx, _ = _get_sandbox(sandbox_id)
        result = sbx.commands.run(
            f"cd /home/user/workspace && {command}",
            timeout=timeout,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.exit_code or 0, output.strip()
    except Exception as e:
        return 1, str(e)


def list_files(sandbox_id: str, path: str = "/home/user/workspace") -> list[dict]:
    """List files in the sandbox filesystem."""
    try:
        sbx, _ = _get_sandbox(sandbox_id)
        entries = sbx.files.list(path)
        return [
            {"name": e.name, "path": e.path, "is_dir": e.is_dir, "size": getattr(e, "size", 0)}
            for e in entries
        ]
    except Exception as e:
        log.warning("E2B list_files error: %s", e)
        return []


def sandbox_status(sandbox_id: Optional[str]) -> str:
    """Check if the sandbox is alive."""
    if not sandbox_id:
        return "stopped"
    try:
        _connect_sandbox(sandbox_id)
        return "running"
    except Exception:
        return "stopped"


async def start_pty(
    agent_id: str,
    sandbox_id: str,
    on_data: Callable[[bytes], None],
    cols: int = 80,
    rows: int = 24,
) -> tuple[object, str]:
    """
    Start an interactive PTY session in the sandbox.
    on_data is called with raw terminal bytes to forward to the browser.
    Returns (terminal, actual_sandbox_id) — sandbox_id may differ if the
    original expired and a new one was provisioned; caller should persist it.
    """
    def _start():
        sbx, actual_id = _get_sandbox(sandbox_id)
        terminal = sbx.pty.create(
            cols=cols,
            rows=rows,
            on_data=on_data,
            timeout=SANDBOX_TIMEOUT,
        )
        terminal.send_input("cd /home/user/workspace && clear\n")
        _pty_sessions[agent_id] = terminal
        return terminal, actual_id

    return await asyncio.to_thread(_start)


def send_pty_input(agent_id: str, data: str):
    """Forward keystrokes from the browser to the PTY."""
    terminal = _pty_sessions.get(agent_id)
    if terminal:
        terminal.send_input(data)


def resize_pty(agent_id: str, cols: int, rows: int):
    """Resize the PTY when the browser terminal resizes."""
    terminal = _pty_sessions.get(agent_id)
    if terminal:
        try:
            terminal.resize(cols=cols, rows=rows)
        except Exception:
            pass


def kill_pty(agent_id: str):
    """Close the PTY session (sandbox stays alive)."""
    terminal = _pty_sessions.pop(agent_id, None)
    if terminal:
        try:
            terminal.kill()
        except Exception:
            pass
