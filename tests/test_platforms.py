import pytest

from app.schemas.platform import PlatformCreate
from app.schemas.project import ProjectCreate
from app.services import platforms, projects
from app.services.errors import NotFound


@pytest.mark.asyncio
async def test_create_and_list_platform(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PL1"))
    plat = await platforms.create_platform(session, p.id, PlatformCreate(name="Linux"))
    assert plat.id is not None
    rows = await platforms.list_platforms(session, p.id)
    assert [r.name for r in rows] == ["Linux"]


@pytest.mark.asyncio
async def test_create_platform_unknown_project(session):
    with pytest.raises(NotFound):
        await platforms.create_platform(session, 9999, PlatformCreate(name="X"))


@pytest.mark.asyncio
async def test_platform_endpoints(client, auth_headers):
    pc = await client.post(
        "/api/v1/projects", json={"name": "P", "prefix": "PLE"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    create = await client.post(
        f"/api/v1/projects/{pid}/platforms", json={"name": "Win"}, headers=auth_headers
    )
    assert create.status_code == 201
    listed = await client.get(f"/api/v1/projects/{pid}/platforms", headers=auth_headers)
    assert any(p["name"] == "Win" for p in listed.json())
