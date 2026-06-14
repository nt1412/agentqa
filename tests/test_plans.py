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


@pytest.mark.asyncio
async def test_add_and_list_plan_cases(session):
    from app.schemas.suite import SuiteCreate
    from app.schemas.testcase import TestCaseCreate
    from app.services import suites, testcases

    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PC1"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))

    links = await plans.add_cases(session, plan.id, [tc.id])
    assert len(links) == 1
    listed = await plans.list_plan_cases(session, plan.id)
    assert len(listed) == 1
    # the link points at the case's current active version
    assert listed[0].version_id is not None


@pytest.mark.asyncio
async def test_add_case_twice_is_idempotent(session):
    from app.schemas.suite import SuiteCreate
    from app.schemas.testcase import TestCaseCreate
    from app.services import suites, testcases

    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PC2"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    await plans.add_cases(session, plan.id, [tc.id])
    await plans.add_cases(session, plan.id, [tc.id])  # second add must not duplicate
    listed = await plans.list_plan_cases(session, plan.id)
    assert len(listed) == 1


@pytest.mark.asyncio
async def test_remove_plan_case(session):
    from app.schemas.suite import SuiteCreate
    from app.schemas.testcase import TestCaseCreate
    from app.services import suites, testcases

    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PC3"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    await plans.add_cases(session, plan.id, [tc.id])
    await plans.remove_case(session, plan.id, tc.id)
    assert await plans.list_plan_cases(session, plan.id) == []


@pytest.mark.asyncio
async def test_add_cases_endpoint(client, auth_headers, session):
    pc = await client.post(
        "/api/v1/projects", json={"name": "P", "prefix": "PCE"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    sc = await client.post(
        f"/api/v1/projects/{pid}/suites", json={"name": "S"}, headers=auth_headers
    )
    cc = await client.post(
        f"/api/v1/suites/{sc.json()['id']}/cases", json={"name": "c"}, headers=auth_headers
    )
    plan = await client.post(
        f"/api/v1/projects/{pid}/plans", json={"name": "Plan"}, headers=auth_headers
    )
    plan_id = plan.json()["id"]
    add = await client.post(
        f"/api/v1/plans/{plan_id}/cases",
        json={"case_ids": [cc.json()["id"]]},
        headers=auth_headers,
    )
    assert add.status_code == 201
    listed = await client.get(f"/api/v1/plans/{plan_id}/cases", headers=auth_headers)
    assert len(listed.json()) == 1
