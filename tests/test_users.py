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
    assert "create_project" in data["orientation"]


@pytest.mark.asyncio
async def test_list_agents_and_deactivate(session):
    u, key = await users.register_agent(session, login="to-deactivate")
    assert any(a.id == u.id for a in await users.list_agents(session))

    d = await users.deactivate_user(session, u.id)
    assert d.active is False

    # a deactivated identity can no longer authenticate
    from app.services import auth
    from app.services.errors import Unauthorized

    with pytest.raises(Unauthorized):
        await auth.user_from_api_key(session, key)


@pytest.mark.asyncio
async def test_list_and_deactivate_agent_endpoints(client, auth_headers):
    reg = await client.post(
        "/api/v1/users/register-agent", json={"login": "rest-deact"}, headers=auth_headers
    )
    aid = reg.json()["id"]
    lst = await client.get("/api/v1/users/agents", headers=auth_headers)
    assert lst.status_code == 200
    assert any(a["id"] == aid for a in lst.json())

    d = await client.delete(f"/api/v1/users/{aid}", headers=auth_headers)
    assert d.status_code == 200
    assert d.json()["active"] is False


@pytest.mark.asyncio
async def test_register_agent_cold_start_with_enroll_key(client, monkeypatch):
    # an unauthenticated agent can bootstrap its identity with the enrollment secret
    monkeypatch.setenv("AQA_MCP_ENROLL_KEY", "join-123")
    r = await client.post(
        "/api/v1/users/register-agent",
        headers={"X-Enroll-Key": "join-123"},
        json={"login": "cold-agent", "agent_model": "m"},
    )
    assert r.status_code == 201
    assert r.json()["api_key"]


@pytest.mark.asyncio
async def test_register_agent_cold_start_rejected_without_valid_key(client, monkeypatch):
    monkeypatch.setenv("AQA_MCP_ENROLL_KEY", "join-123")
    # no key
    r = await client.post("/api/v1/users/register-agent", json={"login": "ca2"})
    assert r.status_code == 401
    # wrong key
    r2 = await client.post(
        "/api/v1/users/register-agent",
        headers={"X-Enroll-Key": "wrong"},
        json={"login": "ca3"},
    )
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_register_agent_cold_start_fails_closed_without_secret(client, monkeypatch):
    monkeypatch.delenv("AQA_MCP_ENROLL_KEY", raising=False)
    monkeypatch.delenv("AGENTQA_MCP_ENROLL_KEY", raising=False)
    r = await client.post(
        "/api/v1/users/register-agent",
        headers={"X-Enroll-Key": "anything"},
        json={"login": "ca4"},
    )
    assert r.status_code == 401
