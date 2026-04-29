"""
E2B sandbox service — real isolated Linux containers, free tier.

Each agent maps to one persistent E2B sandbox.
sandbox_id is stored in DynamoDB as container_id.

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


def _get_sandbox(sandbox_id: Optional[str] = None):
    """Get or create an E2B sandbox, reconnecting if sandbox_id is known."""
    from e2b import Sandbox
    if sandbox_id:
        try:
            sbx = Sandbox.reconnect(sandbox_id, api_key=E2B_API_KEY)
            sbx.set_timeout(SANDBOX_TIMEOUT)
            return sbx
        except Exception:
            log.info("E2B sandbox %s expired, creating new one", sandbox_id)
    sbx = Sandbox(api_key=E2B_API_KEY, timeout=SANDBOX_TIMEOUT)
    log.info("E2B sandbox created: %s", sbx.sandbox_id)
    return sbx


def provision(sandbox_id: Optional[str] = None) -> str:
    """Create or reconnect an E2B sandbox. Returns the sandbox_id."""
    sbx = _get_sandbox(sandbox_id)
    sbx.commands.run("mkdir -p /home/user/workspace")
    return sbx.sandbox_id


def exec_command(sandbox_id: str, command: str, timeout: int = 30) -> tuple[int, str]:
    """Run a command in the sandbox, return (exit_code, output)."""
    try:
        sbx = _get_sandbox(sandbox_id)
        result = sbx.commands.run(
            f"cd /home/user/workspace && {command}",
            timeout=timeout,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr
        return result.exit_code or 0, output.strip()
    except Exception as e:
        return 1, str(e)


def list_files(sandbox_id: str, path: str = "/home/user/workspace") -> list[dict]:
    """List files in the sandbox filesystem."""
    try:
        sbx = _get_sandbox(sandbox_id)
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
        from e2b import Sandbox
        Sandbox.reconnect(sandbox_id, api_key=E2B_API_KEY)
        return "running"
    except Exception:
        return "stopped"


async def start_pty(
    agent_id: str,
    sandbox_id: str,
    on_data: Callable[[bytes], None],
    cols: int = 80,
    rows: int = 24,
) -> object:
    """
    Start an interactive PTY session in the sandbox.
    on_data is called with raw terminal bytes to forward to the browser.
    Returns the terminal object (call send_input / kill on it).
    """
    def _start():
        sbx = _get_sandbox(sandbox_id)
        terminal = sbx.pty.create(
            cols=cols,
            rows=rows,
            on_data=on_data,
            timeout=SANDBOX_TIMEOUT,
        )
        terminal.send_input("cd /home/user/workspace && clear\n")
        _pty_sessions[agent_id] = terminal
        return terminal

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
