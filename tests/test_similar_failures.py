import pytest

from app import embeddings as emb_mod
from app.schemas.execution import ExecutionCreate
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import evidence, executions, plans, projects, suites, testcases
from tests._embed_helpers import fake_embed


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch):
    monkeypatch.setattr(emb_mod, "is_available", lambda: True)
    monkeypatch.setattr(emb_mod, "embed", fake_embed)


async def _case(session, prefix, name="c"):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name=name))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    return tc, plan


async def _fail(session, tc, plan, notes):
    return await executions.record_execution(
        session,
        ExecutionCreate(case_id=tc.id, plan_id=plan.id, build_name="b", status="fail", notes=notes),
        tester_id=None,
    )


@pytest.mark.asyncio
async def test_similar_failures_finds_matching_reasoning(session):
    a_tc, a_plan = await _case(session, "SF1", "a")
    b_tc, b_plan = await _case(session, "SF2", "b")
    c_tc, c_plan = await _case(session, "SF3", "c")
    await _fail(session, a_tc, a_plan, "null pointer in auth handler")
    await _fail(session, b_tc, b_plan, "null pointer in auth handler")  # identical -> nearest
    await _fail(session, c_tc, c_plan, "totally unrelated timeout error")

    results = await evidence.search_similar_failures(session, a_tc.id, n=5)
    assert len(results) >= 1
    # nearest is case B (identical reasoning text -> distance ~0), not C
    assert results[0].case_id == b_tc.id
    assert results[0].distance < 0.01
    # the target case itself is excluded
    assert all(r.case_id != a_tc.id for r in results)


@pytest.mark.asyncio
async def test_similar_failures_empty_when_no_embedding(session):
    a_tc, a_plan = await _case(session, "SF4", "a")
    # a failure with NO notes/reasoning -> no embedding -> nothing to match on
    await executions.record_execution(
        session,
        ExecutionCreate(case_id=a_tc.id, plan_id=a_plan.id, build_name="b", status="fail"),
        tester_id=None,
    )
    assert await evidence.search_similar_failures(session, a_tc.id) == []


@pytest.mark.asyncio
async def test_similar_failures_excludes_passing_executions(session):
    # Regression (Phase 2c review I-1): a PASSING execution with identical reasoning
    # must NOT be returned as a "similar failure".
    a_tc, a_plan = await _case(session, "SF5", "a")
    b_tc, b_plan = await _case(session, "SF6", "b")
    await _fail(session, a_tc, a_plan, "shared boom text")
    # case B records the SAME reasoning text but PASSES -> must be excluded
    await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=b_tc.id,
            plan_id=b_plan.id,
            build_name="b",
            status="pass",
            notes="shared boom text",
        ),
        tester_id=None,
    )
    results = await evidence.search_similar_failures(session, a_tc.id)
    assert all(r.case_id != b_tc.id for r in results)
