"""Lightweight per-agent MCP auth (opt-in via AGENTQA_MCP_REQUIRE_AUTH).

Tests the auth helpers directly rather than driving the full streamable-http
handshake — the same logic _session() enforces on every tool.
"""

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.mcp_server import server as mcp
from app.services import users


def test_request_api_key_reads_x_api_key_header():
    req = Request({"type": "http", "headers": [(b"x-api-key", b"aqa_abc")]})
    token = mcp.request_ctx.set(SimpleNamespace(request=req))
    try:
        assert mcp._request_api_key() == "aqa_abc"
    finally:
        mcp.request_ctx.reset(token)


def test_request_api_key_reads_bearer_header():
    req = Request({"type": "http", "headers": [(b"authorization", b"Bearer aqa_xyz")]})
    token = mcp.request_ctx.set(SimpleNamespace(request=req))
    try:
        assert mcp._request_api_key() == "aqa_xyz"
    finally:
        mcp.request_ctx.reset(token)


def test_request_api_key_none_without_request_context():
    assert mcp._request_api_key() is None


@pytest.mark.asyncio
async def test_auth_disabled_allows_anonymous(session, monkeypatch):
    monkeypatch.delenv("AGENTQA_MCP_REQUIRE_AUTH", raising=False)
    assert await mcp._require_agent(session) is None


@pytest.mark.asyncio
async def test_auth_enabled_rejects_missing_key(session, monkeypatch):
    monkeypatch.setenv("AGENTQA_MCP_REQUIRE_AUTH", "true")
    monkeypatch.setattr(mcp, "_request_api_key", lambda: None)
    with pytest.raises(mcp.AuthRequired):
        await mcp._require_agent(session)


@pytest.mark.asyncio
async def test_auth_enabled_accepts_valid_key(session, monkeypatch):
    u, key = await users.register_agent(session, login="authbot")
    monkeypatch.setenv("AGENTQA_MCP_REQUIRE_AUTH", "true")
    monkeypatch.setattr(mcp, "_request_api_key", lambda: key)
    agent = await mcp._require_agent(session)
    assert agent.id == u.id


@pytest.mark.asyncio
async def test_auth_enabled_rejects_deactivated_key(session, monkeypatch):
    # proves auth and the identity lifecycle connect: deactivate => can't authenticate
    u, key = await users.register_agent(session, login="authbot2")
    await users.deactivate_user(session, u.id)
    monkeypatch.setenv("AGENTQA_MCP_REQUIRE_AUTH", "true")
    monkeypatch.setattr(mcp, "_request_api_key", lambda: key)
    with pytest.raises(mcp.AuthRequired):
        await mcp._require_agent(session)


def test_provenance_override_anti_spoof():
    # authenticated identity overrides a caller-supplied id
    token = mcp._auth_agent.set(SimpleNamespace(id=99))
    try:
        assert mcp._provenance_id(7) == 99
    finally:
        mcp._auth_agent.reset(token)
    # auth disabled (no authenticated agent) -> passed id is used
    assert mcp._provenance_id(7) == 7
