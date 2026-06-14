import datetime as dt

import pytest

from app.schemas.plan import MilestoneCreate, PlanCreate
from app.schemas.project import ProjectCreate
from app.services import milestones, plans, projects
from app.services.errors import NotFound


async def _plan(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    return await plans.create_plan(session, p.id, PlanCreate(name="Plan"))


@pytest.mark.asyncio
async def test_create_and_list_milestone(session):
    plan = await _plan(session, "MS1")
    target = dt.datetime(2026, 7, 1, tzinfo=dt.UTC)
    m = await milestones.create_milestone(
        session, plan.id, MilestoneCreate(name="Beta", target_date=target)
    )
    assert m.id is not None
    rows = await milestones.list_milestones(session, plan.id)
    assert [r.name for r in rows] == ["Beta"]


@pytest.mark.asyncio
async def test_create_milestone_unknown_plan(session):
    with pytest.raises(NotFound):
        await milestones.create_milestone(session, 9999, MilestoneCreate(name="X"))


@pytest.mark.asyncio
async def test_milestone_endpoints(client, auth_headers):
    pc = await client.post(
        "/api/v1/projects", json={"name": "P", "prefix": "MSE"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    plan = await client.post(
        f"/api/v1/projects/{pid}/plans", json={"name": "Plan"}, headers=auth_headers
    )
    plan_id = plan.json()["id"]
    create = await client.post(
        f"/api/v1/plans/{plan_id}/milestones", json={"name": "GA"}, headers=auth_headers
    )
    assert create.status_code == 201
    listed = await client.get(f"/api/v1/plans/{plan_id}/milestones", headers=auth_headers)
    assert any(m["name"] == "GA" for m in listed.json())
