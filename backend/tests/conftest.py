import os

# Set before any app import — controls _USE_DYNAMO and compute mode at module level.
os.environ["AWS_ACCESS_KEY_ID"] = "local"   # triggers in-memory DB branch
os.environ["AGENT_MODE"] = "subprocess"     # skips Docker/EC2 detection
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-prod")
os.environ.pop("EC2_ENABLED", None)

import pytest
from httpx import AsyncClient, ASGITransport
from main import app
import db.dynamo as _dynamo


@pytest.fixture(autouse=True)
def reset_db():
    """Clear in-memory stores between every test for isolation."""
    _dynamo._users_by_id.clear()
    _dynamo._users_by_email.clear()
    _dynamo._agents.clear()
    _dynamo._messages.clear()
    yield


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


_TEST_USER = {"email": "test@axon.dev", "password": "Password1!", "name": "Test User"}


@pytest.fixture
async def auth_headers(client):
    """Sign up a user and return (client, auth headers, user payload)."""
    resp = await client.post("/api/auth/signup", json=_TEST_USER)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    return client, headers, data["user"]
