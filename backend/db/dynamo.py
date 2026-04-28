"""
Dual-mode store:
  - If AWS credentials + DYNAMO_ENDPOINT_URL or real AWS env → DynamoDB
  - Otherwise → thread-safe in-memory dict store (for local dev / demo)
"""

import os
import threading
import logging
from typing import Optional
from collections import defaultdict

log = logging.getLogger(__name__)

_USE_DYNAMO = bool(
    os.getenv("DYNAMO_ENDPOINT_URL") or
    (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_ACCESS_KEY_ID") != "local" and
     os.getenv("AWS_ACCESS_KEY_ID") != "")
)

if _USE_DYNAMO:
    log.info("Storage: DynamoDB")
    import boto3
    _REGION = os.getenv("AWS_REGION", "us-east-1")

    def _table(name: str):
        endpoint = os.getenv("DYNAMO_ENDPOINT_URL")
        kwargs: dict = {"region_name": _REGION}
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        return boto3.resource("dynamodb", **kwargs).Table(name)

    _TABLE_USERS = os.getenv("DYNAMO_USERS_TABLE", "axon-users")
    _TABLE_AGENTS = os.getenv("DYNAMO_AGENTS_TABLE", "axon-agents")
    _TABLE_MESSAGES = os.getenv("DYNAMO_MESSAGES_TABLE", "axon-messages")

    def put_user(user: dict): _table(_TABLE_USERS).put_item(Item=user)

    def get_user_by_id(user_id: str) -> Optional[dict]:
        return _table(_TABLE_USERS).get_item(Key={"id": user_id}).get("Item")

    def get_user_by_email(email: str) -> Optional[dict]:
        resp = _table(_TABLE_USERS).query(
            IndexName="email-index",
            KeyConditionExpression="email = :e",
            ExpressionAttributeValues={":e": email},
            Limit=1,
        )
        items = resp.get("Items", [])
        return items[0] if items else None

    def put_agent(agent: dict): _table(_TABLE_AGENTS).put_item(Item=agent)

    def get_agent(agent_id: str) -> Optional[dict]:
        return _table(_TABLE_AGENTS).get_item(Key={"id": agent_id}).get("Item")

    def list_agents_for_user(user_id: str) -> list[dict]:
        resp = _table(_TABLE_AGENTS).query(
            IndexName="user_id-index",
            KeyConditionExpression="user_id = :u",
            ExpressionAttributeValues={":u": user_id},
        )
        return resp.get("Items", [])

    def update_agent_status(agent_id: str, status: str, container_id: Optional[str] = None):
        expr = "SET #s = :s"
        names = {"#s": "status"}
        vals: dict = {":s": status}
        if container_id is not None:
            expr += ", container_id = :c"
            vals[":c"] = container_id
        _table(_TABLE_AGENTS).update_item(
            Key={"id": agent_id},
            UpdateExpression=expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=vals,
        )

    def delete_agent(agent_id: str): _table(_TABLE_AGENTS).delete_item(Key={"id": agent_id})

    def put_message(msg: dict): _table(_TABLE_MESSAGES).put_item(Item=msg)

    def list_messages_for_agent(agent_id: str, limit: int = 100) -> list[dict]:
        resp = _table(_TABLE_MESSAGES).query(
            IndexName="agent_id-timestamp-index",
            KeyConditionExpression="agent_id = :a",
            ExpressionAttributeValues={":a": agent_id},
            ScanIndexForward=True,
            Limit=limit,
        )
        return resp.get("Items", [])

else:
    log.info("Storage: in-memory (no AWS credentials detected)")

    _lock = threading.Lock()
    _users_by_id: dict[str, dict] = {}
    _users_by_email: dict[str, dict] = {}
    _agents: dict[str, dict] = {}
    _messages: dict[str, list[dict]] = defaultdict(list)

    def put_user(user: dict):
        with _lock:
            _users_by_id[user["id"]] = user
            _users_by_email[user["email"]] = user

    def get_user_by_id(user_id: str) -> Optional[dict]:
        return _users_by_id.get(user_id)

    def get_user_by_email(email: str) -> Optional[dict]:
        return _users_by_email.get(email)

    def put_agent(agent: dict):
        with _lock:
            _agents[agent["id"]] = dict(agent)

    def get_agent(agent_id: str) -> Optional[dict]:
        a = _agents.get(agent_id)
        return dict(a) if a else None

    def list_agents_for_user(user_id: str) -> list[dict]:
        return [dict(a) for a in _agents.values() if a.get("user_id") == user_id]

    def update_agent_status(agent_id: str, status: str, container_id: Optional[str] = None):
        with _lock:
            if agent_id in _agents:
                _agents[agent_id]["status"] = status
                if container_id is not None:
                    _agents[agent_id]["container_id"] = container_id

    def delete_agent(agent_id: str):
        with _lock:
            _agents.pop(agent_id, None)
            _messages.pop(agent_id, None)

    def put_message(msg: dict):
        with _lock:
            _messages[msg["agent_id"]].append(msg)

    def list_messages_for_agent(agent_id: str, limit: int = 100) -> list[dict]:
        msgs = _messages.get(agent_id, [])
        return sorted(msgs, key=lambda m: m.get("timestamp", ""))[-limit:]
