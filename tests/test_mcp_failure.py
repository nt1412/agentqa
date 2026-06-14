import pytest

from app import embeddings as emb_mod
from app.mcp_server import server as mcp
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import plans, projects, suites, testcases
from tests._embed_helpers import fake_embed


@pytest.fixture(autouse=True)
def _setup(session, monkeypatch):
    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(mcp, "_session", lambda: _Ctx())
    monkeypatch.setattr(emb_mod, "is_available", lambda: True)
    monkeypatch.setattr(emb_mod, "embed", fake_embed)


async def _case_plan(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="M", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    return tc, plan


@pytest.mark.asyncio
async def test_failure_context_via_mcp(session):
    tc, plan = await _case_plan(session, "MFC1")
    await mcp.record_test_run(
        case_id=tc.id,
        plan_id=plan.id,
        build_name="b",
        status="fail",
        notes="kaboom",
        reasoning={"t": "x"},
    )
    ctx = await mcp.get_failure_context(case_id=tc.id)
    assert ctx["case_id"] == tc.id
    assert len(ctx["recent_executions"]) == 1


@pytest.mark.asyncio
async def test_similar_failures_via_mcp(session):
    a_tc, a_plan = await _case_plan(session, "MFC2")
    b_tc, b_plan = await _case_plan(session, "MFC3")
    for tc, plan in [(a_tc, a_plan), (b_tc, b_plan)]:
        await mcp.record_test_run(
            case_id=tc.id, plan_id=plan.id, build_name="b", status="fail", notes="same boom"
        )
    res = await mcp.search_similar_failures(case_id=a_tc.id)
    assert any(r["case_id"] == b_tc.id for r in res)
