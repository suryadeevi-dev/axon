"""
WebSocket endpoints:

  /ws/agents/{agent_id}?token=<jwt>            — chat (AI + command loop)
  /ws/agents/{agent_id}/pty?token=<jwt>        — interactive shell emulator

Chat protocol (client → server):
  {"type": "message", "content": "..."}

Chat protocol (server → client):
  {"type": "token",   "data": "..."}   — streaming AI token
  {"type": "command", "data": "..."}   — command being executed
  {"type": "output",  "data": "..."}   — command output chunk
  {"type": "error",   "data": "..."}   — error message
  {"type": "done"}                     — turn complete
  {"type": "status",  "data": {...}}   — agent status update

PTY protocol (client → server):
  {"type": "input",  "data": "<chars>"}
  {"type": "resize", "cols": N, "rows": N}

PTY protocol (server → client):
  {"type": "data",  "data": "<base64 terminal bytes>"}
  {"type": "error", "data": "..."}
"""

import asyncio
import base64
import json
import logging
import re
from datetime import datetime

_CMD_TAG_RE = re.compile(r"<cmd>.*?</cmd>", re.DOTALL)

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from api.auth import decode_token
from db import dynamo
from services import docker_service, ai_service
from observability import ws_connections

log = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/agents/{agent_id}")
async def agent_ws(
    websocket: WebSocket,
    agent_id: str,
    token: str = Query(...),
):
    await websocket.accept()

    try:
        payload = decode_token(token)
        user_id = payload["sub"]
    except Exception:
        await websocket.send_json({"type": "error", "data": "Unauthorized"})
        await websocket.close(code=4001)
        return

    agent = dynamo.get_agent(agent_id)
    if not agent or agent["user_id"] != user_id:
        await websocket.send_json({"type": "error", "data": "Agent not found"})
        await websocket.close(code=4004)
        return

    live_status = docker_service.status(agent_id, agent.get("container_id"))
    await websocket.send_json({"type": "status", "data": {"status": live_status}})

    log.info("WS connected for agent %s user %s", agent_id, user_id)
    ws_connections.labels(ws_type="chat").inc()

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)

            if msg.get("type") != "message":
                continue

            content = msg.get("content", "").strip()
            if not content:
                continue

            user_msg = {
                "id":        f"user-{datetime.utcnow().timestamp()}",
                "agent_id":  agent_id,
                "role":      "user",
                "type":      "text",
                "content":   content,
                "timestamp": datetime.utcnow().isoformat(),
            }
            dynamo.put_message(user_msg)

            history = dynamo.list_messages_for_agent(agent_id, limit=10)
            claude_msgs = [
                {"role": m["role"], "content": m["content"]}
                for m in history
                if m["role"] in ("user", "assistant") and m.get("type") == "text"
            ]

            if not claude_msgs or claude_msgs[-1]["role"] != "user":
                claude_msgs.append({"role": "user", "content": content})

            container_id = agent.get("container_id")

            async def exec_cmd(cmd: str) -> tuple[int, str]:
                return await asyncio.to_thread(
                    docker_service.exec_command, agent_id, cmd, 30, container_id
                )

            assistant_text = ""
            side_records: list[dict] = []
            seq = 0

            async for event in ai_service.run_agent_turn(claude_msgs, exec_cmd):
                await websocket.send_json(event)
                seq += 1
                ts = f"{datetime.utcnow().isoformat()}.{seq:04d}"

                if event["type"] == "token":
                    assistant_text += event["data"]
                elif event["type"] == "command":
                    side_records.append({
                        "id":        f"cmd-{datetime.utcnow().timestamp()}-{seq}",
                        "agent_id":  agent_id,
                        "role":      "assistant",
                        "type":      "command",
                        "content":   event["data"],
                        "timestamp": ts,
                    })
                elif event["type"] == "output":
                    side_records.append({
                        "id":        f"out-{datetime.utcnow().timestamp()}-{seq}",
                        "agent_id":  agent_id,
                        "role":      "assistant",
                        "type":      "output",
                        "content":   event["data"],
                        "timestamp": ts,
                    })

            for record in side_records:
                dynamo.put_message(record)

            clean_text = _CMD_TAG_RE.sub("", assistant_text).strip()
            if clean_text:
                dynamo.put_message({
                    "id":        f"asst-{datetime.utcnow().timestamp()}",
                    "agent_id":  agent_id,
                    "role":      "assistant",
                    "type":      "text",
                    "content":   clean_text,
                    "timestamp": datetime.utcnow().isoformat(),
                })

    except WebSocketDisconnect:
        log.info("WS disconnected for agent %s", agent_id)
    except Exception as e:
        log.exception("WS error for agent %s", agent_id)
        try:
            await websocket.send_json({"type": "error", "data": str(e)})
        except Exception:
            pass
    finally:
        ws_connections.labels(ws_type="chat").dec()


def _pty_send(data: bytes) -> dict:
    return {"type": "data", "data": base64.b64encode(data).decode()}


@router.websocket("/ws/agents/{agent_id}/pty")
async def agent_pty(
    websocket: WebSocket,
    agent_id: str,
    token: str = Query(...),
    cols: int = Query(80),
    rows: int = Query(24),
):
    """
    Shell-emulator terminal over WebSocket. Buffers keystrokes until newline,
    then runs the command via SSM/Docker exec. Tracks cwd across commands.
    No interactive programs (vim, python REPL) — use chat for complex tasks.
    """
    await websocket.accept()

    try:
        payload = decode_token(token)
        user_id = payload["sub"]
    except Exception:
        await websocket.send_json({"type": "error", "data": "Unauthorized"})
        await websocket.close(code=4001)
        return

    agent = dynamo.get_agent(agent_id)
    if not agent or agent["user_id"] != user_id:
        await websocket.send_json({"type": "error", "data": "Agent not found"})
        await websocket.close(code=4004)
        return

    container_id = agent.get("container_id")
    live_status = docker_service.status(agent_id, container_id)
    if live_status != "running":
        await websocket.send_json(_pty_send(b"\r\n\x1b[31m\xe2\x9c\x97 Agent is not running. Start it from the dashboard first.\x1b[0m\r\n"))
        await websocket.close()
        return

    log.info("PTY connected for agent %s user %s", agent_id, user_id)
    ws_connections.labels(ws_type="pty").inc()

    cwd = "/home/axon/workspace"
    PROMPT = b"\x1b[36m$ \x1b[0m"

    # Send initial prompt
    await websocket.send_json(_pty_send(b"\r\n" + PROMPT))

    input_buf = ""

    async def run_cmd(cmd: str) -> tuple[int, str]:
        return await asyncio.to_thread(
            docker_service.exec_command, agent_id, cmd, 30, container_id
        )

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)

            if msg.get("type") == "resize":
                continue  # no TTY resize for SSM

            if msg.get("type") != "input":
                continue

            data: str = msg.get("data", "")

            for char in data:
                if char in ("\r", "\n"):
                    await websocket.send_json(_pty_send(b"\r\n"))
                    cmd = input_buf.strip()
                    input_buf = ""

                    if not cmd:
                        await websocket.send_json(_pty_send(PROMPT))
                        continue

                    if cmd in ("clear", "cls"):
                        await websocket.send_json(_pty_send(b"\x1b[2J\x1b[H" + PROMPT))
                        continue

                    if cmd == "exit" or cmd == "logout":
                        await websocket.send_json(_pty_send(b"Session closed.\r\n"))
                        await websocket.close()
                        return

                    # Handle cd — resolve new cwd via pwd
                    if cmd.startswith("cd") and (len(cmd) == 2 or cmd[2] in (" ", "\t")):
                        target = cmd[2:].strip() or "/home/axon/workspace"
                        exit_code, output = await run_cmd(f"cd {cwd} && cd {target} && pwd")
                        if exit_code == 0:
                            cwd = output.strip()
                            await websocket.send_json(_pty_send(PROMPT))
                        else:
                            out = (output.replace("\n", "\r\n") + "\r\n").encode()
                            await websocket.send_json(_pty_send(out + PROMPT))
                        continue

                    exit_code, output = await run_cmd(f"cd {cwd} && {cmd}")
                    out_text = output.replace("\n", "\r\n")
                    if out_text and not out_text.endswith("\r\n"):
                        out_text += "\r\n"
                    if exit_code != 0 and not out_text.strip():
                        out_text = f"\x1b[31mexit {exit_code}\x1b[0m\r\n"
                    await websocket.send_json(_pty_send(out_text.encode() + PROMPT))

                elif char in ("\x7f", "\x08"):
                    if input_buf:
                        input_buf = input_buf[:-1]
                        await websocket.send_json(_pty_send(b"\x08 \x08"))

                elif char == "\x03":  # Ctrl+C
                    input_buf = ""
                    await websocket.send_json(_pty_send(b"^C\r\n" + PROMPT))

                elif char >= " " or char == "\t":
                    input_buf += char
                    await websocket.send_json(_pty_send(char.encode()))

    except WebSocketDisconnect:
        log.info("PTY disconnected for agent %s", agent_id)
    except Exception as e:
        log.exception("PTY error for agent %s", agent_id)
        try:
            await websocket.send_json({"type": "error", "data": str(e)})
        except Exception:
            pass
    finally:
        ws_connections.labels(ws_type="pty").dec()
