import pytest

from app.schemas.assignment import AssignmentCreate, AssignmentUpdate
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import assignments, plans, projects, suites, testcases


async def _case_and_plan(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    return tc, plan


@pytest.mark.asyncio
async def test_create_and_list_assignment(session, user):
    tc, plan = await _case_and_plan(session, "AS1")
    a = await assignments.create_assignment(
        session,
        AssignmentCreate(
            case_id=tc.id, plan_id=plan.id, assignee_id=user.id, assignee_type="human"
        ),
        assigner_id=user.id,
    )
    assert a.id is not None
    assert a.status == "open"
    rows = await assignments.list_assignments(session, plan_id=plan.id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_list_filters_by_assignee(session, user):
    tc, plan = await _case_and_plan(session, "AS2")
    await assignments.create_assignment(
        session,
        AssignmentCreate(
            case_id=tc.id, plan_id=plan.id, assignee_id=user.id, assignee_type="agent"
        ),
        assigner_id=None,
    )
    mine = await assignments.list_assignments(session, assignee_id=user.id)
    assert len(mine) == 1
    none = await assignments.list_assignments(session, assignee_id=999999)
    assert none == []


@pytest.mark.asyncio
async def test_update_assignment_status(session, user):
    tc, plan = await _case_and_plan(session, "AS3")
    a = await assignments.create_assignment(
        session,
        AssignmentCreate(
            case_id=tc.id, plan_id=plan.id, assignee_id=user.id, assignee_type="human"
        ),
        assigner_id=user.id,
    )
    updated = await assignments.update_assignment(
        session, a.id, AssignmentUpdate(status="in_progress")
    )
    assert updated.status == "in_progress"


@pytest.mark.asyncio
async def test_assignment_endpoints(client, auth_headers, user, session):
    tc, plan = await _case_and_plan(session, "ASE")
    create = await client.post(
        "/api/v1/assignments",
        json={
            "case_id": tc.id,
            "plan_id": plan.id,
            "assignee_id": user.id,
            "assignee_type": "human",
        },
        headers=auth_headers,
    )
    assert create.status_code == 201
    listed = await client.get(f"/api/v1/assignments?plan_id={plan.id}", headers=auth_headers)
    assert len(listed.json()) == 1
