import pytest
from sqlalchemy import select

from app.models.evidence import ExecutionClaim, ExecutionReasoning
from app.schemas.execution import ExecutionCreate
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import executions, plans, projects, suites, testcases


async def _fixture(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    return tc, plan


@pytest.mark.asyncio
async def test_record_execution_persists_claims_and_reasoning(session):
    tc, plan = await _fixture(session, "EV1")
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id,
            plan_id=plan.id,
            build_name="b",
            status="fail",
            claims=["login rejects bad password", "no 500 on empty body"],
            reasoning={"steps": ["checked status code", "inspected body"]},
            agent_model="claude-sonnet-4-6",
            session_id="sess-1",
        ),
        tester_id=None,
    )
    claims = (
        (await session.execute(select(ExecutionClaim).where(ExecutionClaim.execution_id == ex.id)))
        .scalars()
        .all()
    )
    assert {c.claim_text for c in claims} == {"login rejects bad password", "no 500 on empty body"}
    reasoning = (
        await session.execute(
            select(ExecutionReasoning).where(ExecutionReasoning.execution_id == ex.id)
        )
    ).scalar_one()
    assert reasoning.agent_model == "claude-sonnet-4-6"
    assert reasoning.agent_session_id == "sess-1"


@pytest.mark.asyncio
async def test_record_execution_without_claims_is_fine(session):
    tc, plan = await _fixture(session, "EV2")
    ex = await executions.record_execution(
        session,
        ExecutionCreate(case_id=tc.id, plan_id=plan.id, build_name="b", status="pass"),
        tester_id=None,
    )
    claims = (
        (await session.execute(select(ExecutionClaim).where(ExecutionClaim.execution_id == ex.id)))
        .scalars()
        .all()
    )
    assert claims == []
