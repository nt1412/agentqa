"""Minimal REST client shared by the dogfood scripts so they exercise AQA's
public front door (the surface a Bash-tool agent/CI uses), not the service layer.

Auth: AQA_API_KEY (agent key) if set, else admin login (AQA_ADMIN_LOGIN/PASSWORD,
default admin/admin). Base URL: AQA_API_URL (default http://localhost:8000).
"""

import os

import httpx

API = os.environ.get("AQA_API_URL", "http://localhost:8000")
_headers: dict[str, str] = {}


def auth() -> None:
    global _headers
    key = os.environ.get("AQA_API_KEY")
    if key:
        _headers = {"X-API-Key": key}
        return
    login = os.environ.get("AQA_ADMIN_LOGIN", "admin")
    pw = os.environ.get("AQA_ADMIN_PASSWORD", "admin")
    r = httpx.post(f"{API}/api/v1/auth/login", json={"login": login, "password": pw})
    r.raise_for_status()
    _headers = {"Authorization": f"Bearer {r.json()['access_token']}"}


def get(path: str, **params):
    r = httpx.get(API + path, headers=_headers, params=params or None)
    r.raise_for_status()
    return r.json()


def post(path: str, body: dict, **params):
    r = httpx.post(API + path, headers=_headers, json=body, params=params or None)
    r.raise_for_status()
    return r.json()
