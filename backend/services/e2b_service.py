"""
E2B sandbox service — real isolated Linux containers, free tier.

Each agent maps to one persistent E2B sandbox.
sandbox_id is stored in DynamoDB/memory as container_id.

Compute modes (checked in order):
  1. E2B  — if E2B_API_KEY is set
  2. Docker — if Docker socket is available
  3. Subprocess — fallback (Render free tier)

PTY note: on_data callback is only accepted by AsyncSandbox.pty.create() in
e2b 1.x; the sync Sandbox.pty.create() does not have that parameter.
"""

import asyncio
import logging
import os
from typing import Optional, Callable

log = logging.getLogger(__name__)

E2B_API_KEY = os.getenv("E2B_API_KEY", "")
SANDBOX_TIMEOUT = int(os.getenv("E2B_SANDBOX_TIMEOUT", "3600"))

# Active PTY sessions: agent_id → terminal handle
_pty_sessions: dict[str, object] = {}


def e2b_available() -> bool:
    return bool(E2B_API_KEY)


# ── Sync helpers (used for exec / provision / kill) ──────────────────────────

def _sync_connect(sandbox_id: str):
    from e2b import Sandbox
    fn = getattr(Sandbox, "connect", None) or getattr(Sandbox, "reconnect", None)
    return fn(sandbox_id, api_key=E2B_API_KEY, timeout=SANDBOX_TIMEOUT)


def _sync_new():
    from e2b import Sandbox
    sbx = Sandbox(api_key=E2B_API_KEY, timeout=SANDBOX_TIMEOUT)
    log.info("E2B sandbox created: %s", sbx.sandbox_id)
    return sbx


def _get_sandbox(sandbox_id: Optional[str] = None) -> tuple[object, str]:
    """Return (sandbox, actual_id). Creates new sandbox if expired."""
    if sandbox_id:
        try:
            return _sync_connect(sandbox_id), sandbox_id
        except Exception:
            log.info("E2B sandbox %s expired, provisioning new one", sandbox_id)
    sbx = _sync_new()
    return sbx, sbx.sandbox_id


def provision(sandbox_id: Optional[str] = None) -> str:
    sbx, actual_id = _get_sandbox(sandbox_id)
    try:
        sbx.commands.run("mkdir -p /home/user/workspace", timeout=10)
    except Exception:
        pass
    return actual_id


def exec_command(sandbox_id: str, command: str, timeout: int = 30) -> tuple[int, str]:
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
    if not sandbox_id:
        return "stopped"
    try:
        _sync_connect(sandbox_id)
        return "running"
    except Exception:
        return "stopped"


def kill_sandbox(sandbox_id: Optional[str]):
    """Kill the E2B sandbox. Called when an agent is stopped or deleted."""
    if not sandbox_id or not e2b_available():
        return
    try:
        sbx = _sync_connect(sandbox_id)
        sbx.kill()
        log.info("E2B sandbox %s killed", sandbox_id)
    except Exception as e:
        log.info("E2B kill sandbox %s: %s", sandbox_id, e)


# ── Async helpers (PTY — AsyncSandbox required for on_data callback) ─────────

async def _async_connect(sandbox_id: str):
    from e2b import AsyncSandbox
    fn = getattr(AsyncSandbox, "connect", None) or getattr(AsyncSandbox, "reconnect", None)
    return await fn(sandbox_id, api_key=E2B_API_KEY, timeout=SANDBOX_TIMEOUT)


async def _async_new():
    from e2b import AsyncSandbox
    create_fn = getattr(AsyncSandbox, "create", None)
    if create_fn:
        sbx = await create_fn(api_key=E2B_API_KEY, timeout=SANDBOX_TIMEOUT)
    else:
        sbx = await AsyncSandbox(api_key=E2B_API_KEY, timeout=SANDBOX_TIMEOUT)
    log.info("E2B async sandbox created: %s", sbx.sandbox_id)
    return sbx


async def _get_async_sandbox(sandbox_id: Optional[str] = None) -> tuple[object, str]:
    if sandbox_id:
        try:
            return await _async_connect(sandbox_id), sandbox_id
        except Exception:
            log.info("E2B PTY: sandbox %s expired, provisioning new one", sandbox_id)
    sbx = await _async_new()
    return sbx, sbx.sandbox_id


def _make_pty_size(cols: int, rows: int):
    try:
        from e2b import PtySize
        return PtySize(cols=cols, rows=rows)
    except (ImportError, TypeError):
        try:
            from e2b import PtySize
            return PtySize(rows, cols)
        except Exception:
            return {"cols": cols, "rows": rows}


async def start_pty(
    agent_id: str,
    sandbox_id: str,
    on_data: Callable[[bytes], None],
    cols: int = 80,
    rows: int = 24,
) -> tuple[object, str]:
    """
    Start an interactive PTY via AsyncSandbox (required for on_data callback).
    Returns (terminal, actual_sandbox_id).
    """
    sbx, actual_id = await _get_async_sandbox(sandbox_id)

    # PtyOutput wraps raw bytes in e2b 1.x — unwrap before forwarding
    def data_handler(output):
        try:
            raw = getattr(output, "data", output)
            if isinstance(raw, str):
                raw = raw.encode()
            on_data(raw)
        except Exception:
            pass

    size = _make_pty_size(cols, rows)
    terminal = await sbx.pty.create(
        size=size,
        on_data=data_handler,
        timeout=0,
    )

    result = terminal.send_input("cd /home/user/workspace && clear\n")
    if asyncio.iscoroutine(result):
        await result

    _pty_sessions[agent_id] = terminal
    return terminal, actual_id


async def send_pty_input(agent_id: str, data: str):
    terminal = _pty_sessions.get(agent_id)
    if terminal:
        try:
            result = terminal.send_input(data)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            pass


async def resize_pty(agent_id: str, cols: int, rows: int):
    terminal = _pty_sessions.get(agent_id)
    if terminal:
        try:
            size = _make_pty_size(cols, rows)
            result = terminal.resize(size)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            try:
                result = terminal.resize(cols=cols, rows=rows)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass


async def kill_pty(agent_id: str):
    terminal = _pty_sessions.pop(agent_id, None)
    if terminal:
        try:
            result = terminal.kill()
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            pass
