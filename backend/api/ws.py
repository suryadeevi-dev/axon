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
from services import docker_service, ai_service

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
            history = dynamo.list_messages_for_agent(agent_id, limit=20)
            claude_msgs = [
                {"role": m["role"], "content": m["content"]}
                for m in history
                if m["role"] in ("user", "assistant") and m.get("type") == "text"
            ]

            # Ensure last message is from user
            if not claude_msgs or claude_msgs[-1]["role"] != "user":
                claude_msgs.append({"role": "user", "content": content})

            # Exec wrapper
            async def exec_cmd(cmd: str) -> tuple[int, str]:
                return await asyncio.to_thread(docker_service.exec_command, agent_id, cmd)

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
