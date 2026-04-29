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
