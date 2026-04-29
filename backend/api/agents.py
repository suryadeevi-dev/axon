import asyncio
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends

from models.agent import AgentCreate, Agent
from models.user import UserPublic
from api.auth import current_user
from db import dynamo
from services import docker_service, ec2_service
from observability import agent_ops

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def list_agents(user: UserPublic = Depends(current_user)):
    agents = dynamo.list_agents_for_user(user.id)
    for a in agents:
        if a.get("container_id"):
            live_status = docker_service.status(a["id"], a.get("container_id"))
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
    agent_ops.labels(operation="create").inc()
    return {"agent": agent.model_dump()}


@router.get("/{agent_id}")
async def get_agent(agent_id: str, user: UserPublic = Depends(current_user)):
    agent = _get_owned(agent_id, user.id)
    live_status = docker_service.status(agent_id, agent.get("container_id"))
    if live_status != agent.get("status"):
        agent["status"] = live_status
        dynamo.update_agent_status(agent_id, live_status)

    history = dynamo.list_messages_for_agent(agent_id, limit=500)
    return {"agent": agent, "history": history}


@router.post("/{agent_id}/start")
async def start_agent(
    agent_id: str,
    background_tasks: BackgroundTasks,
    user: UserPublic = Depends(current_user),
):
    agent = _get_owned(agent_id, user.id)
    dynamo.update_agent_status(agent_id, "starting")
    try:
        # launch() returns immediately after RunInstances (EC2) or container start (Docker).
        # No SSM wait here — that runs in the background so the HTTP response is instant.
        container_id = await asyncio.to_thread(
            docker_service.launch, agent_id, agent.get("container_id")
        )
        dynamo.update_agent_status(agent_id, "starting", container_id)

        if docker_service._USE_EC2:
            background_tasks.add_task(_wait_ec2_ready, agent_id, container_id)
        else:
            dynamo.update_agent_status(agent_id, "running", container_id)

        agent_ops.labels(operation="start").inc()
        return {"status": "starting", "container_id": container_id}
    except Exception as e:
        dynamo.update_agent_status(agent_id, "error")
        raise HTTPException(status_code=500, detail=f"Failed to start agent: {e}")


async def _wait_ec2_ready(agent_id: str, instance_id: str):
    """Background task: poll SSM until the EC2 instance is ready, then mark running."""
    try:
        await asyncio.to_thread(ec2_service.wait_ready, instance_id)
        dynamo.update_agent_status(agent_id, "running")
        log.info("EC2 agent %s ready (instance %s)", agent_id, instance_id)
    except Exception as e:
        log.warning("EC2 readiness wait failed for agent %s: %s", agent_id, e)
        dynamo.update_agent_status(agent_id, "error")


@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: str, user: UserPublic = Depends(current_user)):
    agent = _get_owned(agent_id, user.id)
    await asyncio.to_thread(docker_service.stop, agent_id, agent.get("container_id"))
    dynamo.update_agent_status(agent_id, "stopped")
    agent_ops.labels(operation="stop").inc()
    return {"status": "stopped"}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, user: UserPublic = Depends(current_user)):
    agent = _get_owned(agent_id, user.id)
    await asyncio.to_thread(docker_service.remove, agent_id, agent.get("container_id"))
    dynamo.delete_agent(agent_id)
    agent_ops.labels(operation="delete").inc()
    return {"deleted": True}


@router.get("/{agent_id}/files")
async def list_agent_files(agent_id: str, user: UserPublic = Depends(current_user)):
    _get_owned(agent_id, user.id)
    if not docker_service._USE_EC2:
        return {"files": [], "path": None}
    files = ec2_service.list_s3_files(agent_id)
    return {"files": files, "path": f"s3://{ec2_service._S3_BUCKET}/agents/{agent_id}/"}


def _get_owned(agent_id: str, user_id: str) -> dict:
    agent = dynamo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your agent")
    return agent
