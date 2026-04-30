"""
Integration tests for agent CRUD and lifecycle endpoints.
docker_service calls are mocked — no Docker or EC2 required.
"""

import pytest
from unittest.mock import patch, AsyncMock


async def _create(client, headers, name="Test Agent", description="desc"):
    resp = await client.post("/api/agents", json={"name": name, "description": description}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["agent"]


class TestCreateAgent:
    async def test_creates_with_stopped_status(self, auth_headers):
        client, headers, _ = auth_headers
        agent = await _create(client, headers)
        assert agent["name"] == "Test Agent"
        assert agent["status"] == "stopped"
        assert "id" in agent

    async def test_requires_auth(self, client):
        resp = await client.post("/api/agents", json={"name": "X"})
        assert resp.status_code == 401


class TestListAgents:
    async def test_empty_list(self, auth_headers):
        client, headers, _ = auth_headers
        resp = await client.get("/api/agents", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["agents"] == []

    async def test_returns_own_agents(self, auth_headers):
        client, headers, _ = auth_headers
        await _create(client, headers, "Agent A")
        await _create(client, headers, "Agent B")
        resp = await client.get("/api/agents", headers=headers)
        names = [a["name"] for a in resp.json()["agents"]]
        assert "Agent A" in names
        assert "Agent B" in names

    async def test_requires_auth(self, client):
        resp = await client.get("/api/agents")
        assert resp.status_code == 401


class TestGetAgent:
    async def test_success(self, auth_headers):
        client, headers, _ = auth_headers
        agent = await _create(client, headers)
        resp = await client.get(f"/api/agents/{agent['id']}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["agent"]["id"] == agent["id"]

    async def test_not_found(self, auth_headers):
        client, headers, _ = auth_headers
        resp = await client.get("/api/agents/does-not-exist", headers=headers)
        assert resp.status_code == 404

    async def test_other_users_agent_is_403(self, client):
        # User 1 creates an agent
        r1 = await client.post("/api/auth/signup", json={"email": "u1@axon.dev", "password": "Password1!", "name": "U1"})
        h1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}
        agent = await _create(client, h1)

        # User 2 tries to access it
        r2 = await client.post("/api/auth/signup", json={"email": "u2@axon.dev", "password": "Password1!", "name": "U2"})
        h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
        resp = await client.get(f"/api/agents/{agent['id']}", headers=h2)
        assert resp.status_code == 403


class TestStartAgent:
    async def test_start_subprocess_mode(self, auth_headers):
        client, headers, _ = auth_headers
        agent = await _create(client, headers)

        with patch("api.agents.docker_service.launch", return_value="subprocess:abc123"), \
             patch("api.agents.docker_service._USE_EC2", False):
            resp = await client.post(f"/api/agents/{agent['id']}/start", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "starting"
        assert body["container_id"] == "subprocess:abc123"

    async def test_start_propagates_launch_error(self, auth_headers):
        client, headers, _ = auth_headers
        agent = await _create(client, headers)

        with patch("api.agents.docker_service.launch", side_effect=RuntimeError("boom")), \
             patch("api.agents.docker_service._USE_EC2", False):
            resp = await client.post(f"/api/agents/{agent['id']}/start", headers=headers)

        assert resp.status_code == 500
        assert "boom" in resp.json()["detail"]

    async def test_start_not_found(self, auth_headers):
        client, headers, _ = auth_headers
        resp = await client.post("/api/agents/ghost/start", headers=headers)
        assert resp.status_code == 404


class TestStopAgent:
    async def test_stop_success(self, auth_headers):
        client, headers, _ = auth_headers
        agent = await _create(client, headers)

        with patch("api.agents.docker_service.stop"):
            resp = await client.post(f"/api/agents/{agent['id']}/stop", headers=headers)

        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"


class TestDeleteAgent:
    async def test_delete_success(self, auth_headers):
        client, headers, _ = auth_headers
        agent = await _create(client, headers)

        with patch("api.agents.docker_service.remove"):
            resp = await client.delete(f"/api/agents/{agent['id']}", headers=headers)

        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Confirm it's gone
        resp2 = await client.get(f"/api/agents/{agent['id']}", headers=headers)
        assert resp2.status_code == 404

    async def test_delete_other_users_agent_is_403(self, client):
        r1 = await client.post("/api/auth/signup", json={"email": "d1@axon.dev", "password": "Password1!", "name": "D1"})
        h1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}
        agent = await _create(client, h1)

        r2 = await client.post("/api/auth/signup", json={"email": "d2@axon.dev", "password": "Password1!", "name": "D2"})
        h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}

        with patch("api.agents.docker_service.remove"):
            resp = await client.delete(f"/api/agents/{agent['id']}", headers=h2)
        assert resp.status_code == 403


class TestAgentFiles:
    async def test_files_returns_empty_without_s3(self, auth_headers):
        client, headers, _ = auth_headers
        agent = await _create(client, headers)

        with patch("api.agents.ec2_service.list_s3_files", return_value=[]), \
             patch("api.agents.docker_service._USE_EC2", False):
            resp = await client.get(f"/api/agents/{agent['id']}/files", headers=headers)

        assert resp.status_code == 200
        assert resp.json()["files"] == []
