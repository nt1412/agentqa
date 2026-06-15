import pytest
from sqlalchemy import select

from app.models.plan import TestPlan
from app.models.user import Assignment
from app.schemas.execution import ExecutionCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import assignments, executions, plans, projects, reruns, suites, testcases


async def _setup(session, prefix, n=2):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    suite = await suites.create_suite(session, p.id, SuiteCreate(name="Root"))
    cases = [
        await testcases.create_test_case(session, suite.id, TestCaseCreate(name=f"c{i}"))
        for i in range(n)
    ]
    plan = TestPlan(project_id=p.id, name="Plan")
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return p, cases, plan


@pytest.mark.asyncio
async def test_request_rerun_for_case_is_idempotent(session, user):
    _, cases, plan = await _setup(session, "RR1")
    await plans.add_cases(session, plan.id, [c.id for c in cases])
    ex = await executions.record_execution(
        session,
        ExecutionCreate(case_id=cases[0].id, plan_id=plan.id, build_name="b1", status="fail"),
        tester_id=None,
    )
    a1 = await reruns.request_rerun(
        session, build_id=ex.build_id, case_id=cases[0].id,
        assignee_id=user.id, assigner_id=user.id,
    )
    assert len(a1) == 1
    assert a1[0].type == "rerun"
    assert a1[0].build_id == ex.build_id
    assert a1[0].status == "open"

    # second request for the same (case, build) is a no-op (no duplicate open rerun)
    a2 = await reruns.request_rerun(
        session, build_id=ex.build_id, case_id=cases[0].id,
        assignee_id=user.id, assigner_id=user.id,
    )
    assert a2 == []
    rows = (
        await session.execute(
            select(Assignment).where(
                Assignment.type == "rerun", Assignment.build_id == ex.build_id
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_request_rerun_for_whole_build_and_agent_discovery(session, user):
    _, cases, plan = await _setup(session, "RR2", n=3)
    await plans.add_cases(session, plan.id, [c.id for c in cases])
    ex = await executions.record_execution(
        session,
        ExecutionCreate(case_id=cases[0].id, plan_id=plan.id, build_name="b1", status="fail"),
        tester_id=None,
    )
    created = await reruns.request_rerun(
        session, build_id=ex.build_id, assignee_id=user.id, assigner_id=user.id
    )
    assert len(created) == 3  # one rerun per plan case

    # agents discover the requests through the existing assignments queue (REQ-RERUN-3)
    found = await assignments.list_assignments(session, plan_id=plan.id)
    assert len([a for a in found if a.type == "rerun"]) == 3


@pytest.mark.asyncio
async def test_request_rerun_over_rest(session, client, auth_headers, user):
    _, cases, plan = await _setup(session, "RR3")
    await plans.add_cases(session, plan.id, [c.id for c in cases])
    ex = await executions.record_execution(
        session,
        ExecutionCreate(case_id=cases[0].id, plan_id=plan.id, build_name="b1", status="fail"),
        tester_id=None,
    )
    r = await client.post(
        f"/api/v1/builds/{ex.build_id}/rerun",
        headers=auth_headers,
        json={"assignee_id": user.id, "case_id": cases[0].id},
    )
    assert r.status_code == 201
    body = r.json()
    assert len(body) == 1
    assert body[0]["build_id"] == ex.build_id
    assert body[0]["status"] == "open"
