import pytest

from app.mcp_server import server as mcp
from app.models.plan import TestPlan
from app.schemas.execution import ExecutionCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import executions, plans, projects, suites, testcases


@pytest.fixture(autouse=True)
def _use_test_session(session, monkeypatch):
    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(mcp, "_session", lambda *a, **k: _Ctx())


@pytest.mark.asyncio
async def test_lineage_tools_via_mcp(session):
    p = await projects.create_project(session, ProjectCreate(name="ML", prefix="MLIN"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = TestPlan(project_id=p.id, name="Plan")
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    await plans.add_cases(session, plan.id, [tc.id])
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id, plan_id=plan.id, build_name="b1", status="pass",
            commit_id="sha1", branch="main",
        ),
        tester_id=None,
    )

    tl = await mcp.list_build_timeline(plan_id=plan.id)
    assert tl[0]["commit_id"] == "sha1"
    assert tl[0]["rollup"]["pass"] == 1

    detail = await mcp.get_build_detail(build_id=ex.build_id)
    assert detail["rollup"]["pass"] == 1
    assert detail["build"]["branch"] == "main"

    hist = await mcp.get_case_history(case_id=tc.id)
    assert hist["executions"][0]["commit_id"] == "sha1"
