import pytest

from app.schemas.plan import PlanCreate, PlanUpdate
from app.schemas.project import ProjectCreate
from app.services import plans, projects
from app.services.errors import NotFound


@pytest.mark.asyncio
async def test_create_and_get_plan(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PN1"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Release 1"))
    assert plan.id is not None
    fetched = await plans.get_plan(session, plan.id)
    assert fetched.name == "Release 1"
    assert fetched.is_open is True


@pytest.mark.asyncio
async def test_create_plan_unknown_project(session):
    with pytest.raises(NotFound):
        await plans.create_plan(session, 9999, PlanCreate(name="X"))


@pytest.mark.asyncio
async def test_update_plan(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PN2"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="A"))
    updated = await plans.update_plan(session, plan.id, PlanUpdate(is_open=False))
    assert updated.is_open is False
    assert updated.name == "A"


@pytest.mark.asyncio
async def test_list_plans(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PN3"))
    await plans.create_plan(session, p.id, PlanCreate(name="A"))
    await plans.create_plan(session, p.id, PlanCreate(name="B"))
    rows = await plans.list_plans(session, p.id)
    assert {r.name for r in rows} == {"A", "B"}


@pytest.mark.asyncio
async def test_plan_endpoints(client, auth_headers):
    pc = await client.post(
        "/api/v1/projects", json={"name": "P", "prefix": "PNE"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    create = await client.post(
        f"/api/v1/projects/{pid}/plans", json={"name": "Sprint 1"}, headers=auth_headers
    )
    assert create.status_code == 201
    plan_id = create.json()["id"]
    got = await client.get(f"/api/v1/plans/{plan_id}", headers=auth_headers)
    assert got.json()["name"] == "Sprint 1"
