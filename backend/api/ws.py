"""
WebSocket endpoint: /ws/agents/{agent_id}?token=<jwt>

Protocol (client → server):
  {"type": "message", "content": "..."}

Protocol (server → client):
  {"type": "token",   "data": "..."}   — streaming AI token
  {"type": "command", "data": "..."}   — command being executed
  {"type": "output",  "data": "..."}   — command output chunk
  {"type": "error",   "data": "..."}   — error message
  {"type": "done"}                     — turn complete
  {"type": "status",  "data": {...}}   — agent status update
"""

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from api.auth import decode_token
from db import dynamo
from services import docker_service, ai_service, e2b_service

log = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/agents/{agent_id}")
async def agent_ws(
    websocket: WebSocket,
    agent_id: str,
    token: str = Query(...),
):
    await websocket.accept()

    # Auth
    try:
        payload = decode_token(token)
        user_id = payload["sub"]
    except Exception:
        await websocket.send_json({"type": "error", "data": "Unauthorized"})
        await websocket.close(code=4001)
        return

    # Verify agent ownership
    agent = dynamo.get_agent(agent_id)
    if not agent or agent["user_id"] != user_id:
        await websocket.send_json({"type": "error", "data": "Agent not found"})
        await websocket.close(code=4004)
        return

    # Send current status
    live_status = docker_service.status(agent_id)
    await websocket.send_json({"type": "status", "data": {"status": live_status}})

    log.info("WS connected for agent %s user %s", agent_id, user_id)

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)

            if msg.get("type") != "message":
                continue

            content = msg.get("content", "").strip()
            if not content:
                continue

            # Persist user message
            user_msg = {
                "id": f"user-{datetime.utcnow().timestamp()}",
                "agent_id": agent_id,
                "role": "user",
                "type": "text",
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            }
            dynamo.put_message(user_msg)

            # Build context (last 20 messages for the AI)
            history = dynamo.list_messages_for_agent(agent_id, limit=10)
            claude_msgs = [
                {"role": m["role"], "content": m["content"]}
                for m in history
                if m["role"] in ("user", "assistant") and m.get("type") == "text"
            ]

            # Ensure last message is from user
            if not claude_msgs or claude_msgs[-1]["role"] != "user":
                claude_msgs.append({"role": "user", "content": content})

            # Exec wrapper — passes sandbox/container ID for E2B mode
            container_id = agent.get("container_id")
            async def exec_cmd(cmd: str) -> tuple[int, str]:
                return await asyncio.to_thread(docker_service.exec_command, agent_id, cmd, 30, container_id)

            # Run agent turn
            assistant_text = ""
            async for event in ai_service.run_agent_turn(claude_msgs, exec_cmd):
                await websocket.send_json(event)
                if event["type"] == "token":
                    assistant_text += event["data"]

            # Persist assistant response
            if assistant_text:
                asst_msg = {
                    "id": f"asst-{datetime.utcnow().timestamp()}",
                    "agent_id": agent_id,
                    "role": "assistant",
                    "type": "text",
                    "content": assistant_text,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                dynamo.put_message(asst_msg)

    except WebSocketDisconnect:
        log.info("WS disconnected for agent %s", agent_id)
    except Exception as e:
        log.exception("WS error for agent %s", agent_id)
        try:
            await websocket.send_json({"type": "error", "data": str(e)})
        except Exception:
            pass


@router.websocket("/ws/agents/{agent_id}/pty")
async def agent_pty(
    websocket: WebSocket,
    agent_id: str,
    token: str = Query(...),
    cols: int = Query(default=80),
    rows: int = Query(default=24),
):
    """
    Interactive PTY terminal (xterm.js ↔ E2B sandbox).
    Only available when E2B_API_KEY is set.
    Messages from browser: raw keystroke bytes (text frame)
    Messages to browser:   {"type":"data","data":"<base64>"} — terminal output
                           {"type":"resize","cols":n,"rows":n} — ack
                           {"type":"error","data":"..."}
    """
    await websocket.accept()

    if not e2b_service.e2b_available():
        await websocket.send_json({"type": "error", "data": "PTY requires E2B — set E2B_API_KEY"})
        await websocket.close()
        return

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

    sandbox_id = agent.get("container_id")
    if not sandbox_id:
        await websocket.send_json({"type": "error", "data": "Agent has no sandbox — start the agent first"})
        await websocket.close()
        return

    # Buffer PTY output and forward to WebSocket
    output_queue: asyncio.Queue = asyncio.Queue()

    def on_pty_data(data: bytes):
        try:
            if isinstance(data, str):
                data = data.encode()
            import base64
            output_queue.put_nowait(base64.b64encode(data).decode())
        except Exception:
            pass

    try:
        terminal = await e2b_service.start_pty(agent_id, sandbox_id, on_pty_data, cols, rows)
        log.info("PTY started for agent %s", agent_id)

        # Forward PTY output to browser
        async def forward_output():
            while True:
                try:
                    data = await asyncio.wait_for(output_queue.get(), timeout=30)
                    await websocket.send_json({"type": "data", "data": data})
                except asyncio.TimeoutError:
                    # keepalive
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

        forward_task = asyncio.create_task(forward_output())

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                    if msg.get("type") == "resize":
                        e2b_service.resize_pty(agent_id, msg.get("cols", 80), msg.get("rows", 24))
                    elif msg.get("type") == "input":
                        e2b_service.send_pty_input(agent_id, msg.get("data", ""))
                except json.JSONDecodeError:
                    # plain text = keystroke data
                    e2b_service.send_pty_input(agent_id, raw)
        except WebSocketDisconnect:
            log.info("PTY disconnected for agent %s", agent_id)
        finally:
            forward_task.cancel()
            e2b_service.kill_pty(agent_id)

    except Exception as e:
        log.exception("PTY error for agent %s", agent_id)
        try:
            await websocket.send_json({"type": "error", "data": str(e)})
        except Exception:
            pass
