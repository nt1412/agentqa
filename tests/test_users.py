import pytest

from app.services import auth, users
from app.services.errors import Conflict


@pytest.mark.asyncio
async def test_register_agent_creates_agent_identity(session):
    user, api_key = await users.register_agent(
        session, login="qa-bot", agent_model="claude-opus-4-8"
    )
    assert user.id is not None
    assert user.auth_method == "agent"
    assert user.agent_model == "claude-opus-4-8"
    assert user.active is True
    # plaintext key is returned, only the hash is stored
    assert api_key.startswith("aqa_")
    assert user.api_key == auth.hash_api_key(api_key)
    assert user.api_key != api_key


@pytest.mark.asyncio
async def test_register_agent_key_authenticates(session):
    user, api_key = await users.register_agent(session, login="qa-bot-2")
    resolved = await auth.user_from_api_key(session, api_key)
    assert resolved.id == user.id


@pytest.mark.asyncio
async def test_register_agent_duplicate_login_conflicts(session):
    await users.register_agent(session, login="dupe")
    with pytest.raises(Conflict):
        await users.register_agent(session, login="dupe")


@pytest.mark.asyncio
async def test_register_agent_endpoint(client, auth_headers):
    resp = await client.post(
        "/api/v1/users/register-agent",
        json={"login": "rest-bot", "agent_model": "claude-opus-4-8"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] is not None
    assert data["auth_method"] == "agent"
    assert data["api_key"].startswith("aqa_")
    assert "RECOMMENDED WORKFLOW" in data["orientation"]
