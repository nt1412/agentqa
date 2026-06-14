import pytest

from app.mcp_server import server as mcp
from app.models.plan import TestPlan
from app.schemas.project import ProjectCreate
from app.services import projects


@pytest.fixture(autouse=True)
def _use_test_session(session, monkeypatch):
    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(mcp, "_session", lambda: _Ctx())


async def _plan(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="M", prefix=prefix))
    plan = TestPlan(project_id=p.id, name="Plan")
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return p, plan


@pytest.mark.asyncio
async def test_create_test_plan_tool(session):
    p = await projects.create_project(session, ProjectCreate(name="CP", prefix="CPT"))
    plan = await mcp.create_test_plan(project_id=p.id, name="Smoke", notes="n")
    assert plan["id"] is not None
    assert plan["name"] == "Smoke"
    # the returned id is usable by the other hierarchy tools
    added = await mcp.add_cases_to_plan(plan_id=plan["id"], case_ids=[])
    assert added == []


@pytest.mark.asyncio
async def test_get_suite_tree_tool(session):
    p, _ = await _plan(session, "HT1")
    await mcp.create_test_suite(project_id=p.id, path="Purple/SOC")
    await mcp.create_test_case(project_id=p.id, suite_path="Purple/SOC", name="alert")
    tree = await mcp.get_suite_tree(project_id=p.id)
    assert tree[0]["name"] == "Purple"
    soc = tree[0]["children"][0]
    assert soc["name"] == "SOC"
    assert soc["case_count"] == 1


@pytest.mark.asyncio
async def test_add_cases_and_run_manifest_tool(session):
    p, plan = await _plan(session, "HT2")
    await mcp.create_test_suite(project_id=p.id, path="S")
    a = await mcp.create_test_case(project_id=p.id, suite_path="S", name="recon")
    b = await mcp.create_test_case(project_id=p.id, suite_path="S", name="exploit")

    added = await mcp.add_cases_to_plan(plan_id=plan.id, case_ids=[a["id"], b["id"]], urgency=3)
    assert [x["order"] for x in added] == [1, 2]

    # exploit depends on recon
    dep = await mcp.add_test_dependency(case_id=b["id"], depends_on_case_id=a["id"])
    assert dep["relation_type"] == "depends_on"

    manifest = {m["case_id"]: m for m in await mcp.get_run_manifest(plan_id=plan.id)}
    assert manifest[b["id"]]["runnable"] is False
    assert manifest[b["id"]]["blocked_by"] == [a["id"]]
    assert manifest[a["id"]]["runnable"] is True
    assert manifest[a["id"]]["urgency"] == 3
