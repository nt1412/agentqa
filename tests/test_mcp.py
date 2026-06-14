import pytest

from app.mcp_server import server as mcp
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


@pytest.mark.asyncio
async def test_create_test_suite_by_path(session):
    p = await projects.create_project(session, ProjectCreate(name="M", prefix="MCP"))
    result = await mcp.create_test_suite(project_id=p.id, path="A/B/C")
    assert result["name"] == "C"
    assert result["id"] is not None


@pytest.mark.asyncio
async def test_create_and_get_test_case(session):
    p = await projects.create_project(session, ProjectCreate(name="M2", prefix="MC2"))
    await mcp.create_test_suite(project_id=p.id, path="Root")
    case = await mcp.create_test_case(
        project_id=p.id,
        suite_path="Root",
        name="login",
        summary="s",
        steps=[{"action": "go", "expected_result": "ok"}],
    )
    fetched = await mcp.get_test_case(case_id=case["id"])
    assert fetched["name"] == "login"
    assert fetched["current_version"]["steps"][0]["action"] == "go"


@pytest.mark.asyncio
async def test_bulk_create(session):
    p = await projects.create_project(session, ProjectCreate(name="M3", prefix="MC3"))
    result = await mcp.bulk_create_test_cases(
        project_id=p.id,
        suite_path="Bulk",
        cases=[{"name": "a"}, {"name": "b"}],
    )
    assert len(result) == 2


@pytest.mark.asyncio
async def test_search(session):
    p = await projects.create_project(session, ProjectCreate(name="M4", prefix="MC4"))
    await mcp.create_test_suite(project_id=p.id, path="S")
    await mcp.create_test_case(project_id=p.id, suite_path="S", name="payment test")
    results = await mcp.search_test_cases(project_id=p.id, query="payment")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_record_test_run(session):
    p = await projects.create_project(session, ProjectCreate(name="M5", prefix="MC5"))
    await mcp.create_test_suite(project_id=p.id, path="S")
    case = await mcp.create_test_case(project_id=p.id, suite_path="S", name="c")
    from app.models.plan import TestPlan

    plan = TestPlan(project_id=p.id, name="P")
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    run = await mcp.record_test_run(
        case_id=case["id"],
        plan_id=plan.id,
        build_name="b1",
        status="pass",
    )
    assert run["status"] == "pass"
    assert run["build_id"] is not None
