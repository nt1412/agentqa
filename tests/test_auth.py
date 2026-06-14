import pytest

from app.services import auth
from app.services.errors import Unauthorized


def test_hash_and_verify_password():
    h = auth.hash_password("hunter2")
    assert h != "hunter2"
    assert auth.verify_password("hunter2", h) is True
    assert auth.verify_password("wrong", h) is False


def test_jwt_roundtrip():
    token = auth.create_access_token(user_id=42)
    assert auth.decode_token(token) == 42


def test_decode_invalid_token_raises():
    with pytest.raises(Unauthorized):
        auth.decode_token("not.a.jwt")


def test_generate_api_key_is_unique_and_prefixed():
    k1 = auth.generate_api_key()
    k2 = auth.generate_api_key()
    assert k1.startswith("aqa_")
    assert k1 != k2


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_success(client, user):
    resp = await client.post("/api/v1/auth/login", json={"login": "alice", "password": "pw"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_bad_password(client, user):
    resp = await client.post("/api/v1/auth/login", json={"login": "alice", "password": "nope"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_token(client, auth_headers):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["login"] == "alice"


@pytest.mark.asyncio
async def test_api_key_issue_and_use(client, auth_headers):
    issued = await client.post("/api/v1/auth/token", headers=auth_headers)
    assert issued.status_code == 200
    key = issued.json()["api_key"]
    assert key.startswith("aqa_")
    resp = await client.get("/api/v1/auth/me", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json()["login"] == "alice"


def test_prod_requires_jwt_secret(monkeypatch):
    import app.config
    from app.main import create_app

    app.config.get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("JWT_SECRET", "change-me-in-production")
    with pytest.raises(RuntimeError):
        create_app()
    app.config.get_settings.cache_clear()
