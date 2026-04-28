from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import uuid
import asyncio

from models.agent import AgentCreate, Agent
from models.user import UserPublic
from api.auth import current_user
from db import dynamo
from services import docker_service

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def list_agents(user: UserPublic = Depends(current_user)):
    agents = dynamo.list_agents_for_user(user.id)
    # Refresh container status from Docker
    for a in agents:
        if a.get("container_id"):
            live_status = docker_service.status(a["id"])
            if live_status != a.get("status"):
                a["status"] = live_status
                dynamo.update_agent_status(a["id"], live_status)
    return {"agents": sorted(agents, key=lambda x: x.get("created_at", ""), reverse=True)}


@router.post("")
async def create_agent(body: AgentCreate, user: UserPublic = Depends(current_user)):
    agent = Agent(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name=body.name,
        description=body.description,
        status="stopped",
    )
    dynamo.put_agent(agent.model_dump())
    return {"agent": agent.model_dump()}


@router.get("/{agent_id}")
async def get_agent(agent_id: str, user: UserPublic = Depends(current_user)):
    agent = _get_owned(agent_id, user.id)
    # Refresh status
    live_status = docker_service.status(agent_id)
    if live_status != agent.get("status"):
        agent["status"] = live_status
        dynamo.update_agent_status(agent_id, live_status)

    history = dynamo.list_messages_for_agent(agent_id, limit=200)
    return {"agent": agent, "history": history}


@router.post("/{agent_id}/start")
async def start_agent(agent_id: str, user: UserPublic = Depends(current_user)):
    agent = _get_owned(agent_id, user.id)
    dynamo.update_agent_status(agent_id, "starting")
    try:
        container_id = await asyncio.to_thread(docker_service.start, agent_id)
        dynamo.update_agent_status(agent_id, "running", container_id)
        return {"status": "running", "container_id": container_id}
    except Exception as e:
        dynamo.update_agent_status(agent_id, "error")
        raise HTTPException(status_code=500, detail=f"Failed to start agent: {e}")


@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: str, user: UserPublic = Depends(current_user)):
    _get_owned(agent_id, user.id)
    await asyncio.to_thread(docker_service.stop, agent_id)
    dynamo.update_agent_status(agent_id, "stopped")
    return {"status": "stopped"}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, user: UserPublic = Depends(current_user)):
    _get_owned(agent_id, user.id)
    await asyncio.to_thread(docker_service.remove, agent_id)
    dynamo.delete_agent(agent_id)
    return {"deleted": True}


def _get_owned(agent_id: str, user_id: str) -> dict:
    agent = dynamo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your agent")
    return agent
