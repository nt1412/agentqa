import pytest

from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.services import projects, suites
from app.services.errors import NotFound


@pytest.mark.asyncio
async def test_create_suite(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="P1"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="Auth"))
    assert s.id is not None
    assert s.parent_id is None


@pytest.mark.asyncio
async def test_find_or_create_path_creates_chain(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="P2"))
    leaf = await suites.find_or_create_path(session, p.id, "Auth/Login/OAuth")
    assert leaf.name == "OAuth"
    # second call must reuse, not duplicate
    leaf2 = await suites.find_or_create_path(session, p.id, "Auth/Login/OAuth")
    assert leaf2.id == leaf.id
    all_suites = await suites.list_suites(session, p.id)
    names = sorted(s.name for s in all_suites)
    assert names == ["Auth", "Login", "OAuth"]


@pytest.mark.asyncio
async def test_get_tree(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="P3"))
    await suites.find_or_create_path(session, p.id, "A/B")
    tree = await suites.get_tree(session, p.id)
    assert len(tree) == 1
    assert tree[0].name == "A"
    assert tree[0].children[0].name == "B"


@pytest.mark.asyncio
async def test_create_suite_unknown_project_raises(session):
    with pytest.raises(NotFound):
        await suites.create_suite(session, 9999, SuiteCreate(name="X"))


@pytest.mark.asyncio
async def test_suite_endpoints(client, auth_headers, session):
    pc = await client.post(
        "/api/v1/projects", json={"name": "S", "prefix": "SX"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    sc = await client.post(
        f"/api/v1/projects/{pid}/suites", json={"name": "Root"}, headers=auth_headers
    )
    assert sc.status_code == 201
    tree = await client.get(f"/api/v1/suites/{sc.json()['id']}/tree", headers=auth_headers)
    assert tree.status_code == 200
