import pytest

from app.mcp_server import server as mcp
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import plans, projects, suites, testcases


@pytest.fixture(autouse=True)
def _use_test_session(session, monkeypatch):
    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(mcp, "_session", lambda: _Ctx())


@pytest.mark.asyncio
async def test_assign_and_list_via_mcp(session, user):
    p = await projects.create_project(session, ProjectCreate(name="M", prefix="MAS"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))

    res = await mcp.assign_test(
        case_id=tc.id, plan_id=plan.id, assignee_id=user.id, assignee_type="agent"
    )
    assert res["status"] == "open"
    rows = await mcp.list_assignments(plan_id=plan.id)
    assert len(rows) == 1
    assert rows[0]["assignee_id"] == user.id
