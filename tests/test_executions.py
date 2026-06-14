import pytest

from app.models.plan import TestPlan
from app.schemas.execution import ExecutionCreate, StepResultIn
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import StepIn, TestCaseCreate
from app.services import executions, projects, suites, testcases
from app.services.errors import NotFound


async def _fixture(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(
        session,
        s.id,
        TestCaseCreate(name="c", steps=[StepIn(action="a1"), StepIn(action="a2")]),
    )
    plan = TestPlan(project_id=p.id, name="Plan")
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return p, s, tc, plan


@pytest.mark.asyncio
async def test_record_execution_upserts_build(session):
    p, s, tc, plan = await _fixture(session, "EX1")
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id,
            plan_id=plan.id,
            build_name="build-42",
            commit_id="abc123",
            status="pass",
        ),
        tester_id=None,
    )
    assert ex.build_id is not None
    ex2 = await executions.record_execution(
        session,
        ExecutionCreate(case_id=tc.id, plan_id=plan.id, build_name="build-42", status="fail"),
        tester_id=None,
    )
    assert ex2.build_id == ex.build_id


@pytest.mark.asyncio
async def test_record_with_step_results(session):
    p, s, tc, plan = await _fixture(session, "EX2")
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id,
            plan_id=plan.id,
            build_name="b",
            status="fail",
            step_results=[
                StepResultIn(step_number=1, status="pass"),
                StepResultIn(step_number=2, status="fail", notes="boom"),
            ],
        ),
        tester_id=None,
    )
    assert len(ex.steps) == 2


@pytest.mark.asyncio
async def test_record_by_external_id(session):
    p, s, tc, plan = await _fixture(session, "EX3")
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            external_id="EX3-1",
            project_id=p.id,
            plan_id=plan.id,
            build_name="b",
            status="pass",
        ),
        tester_id=None,
    )
    assert ex.id is not None


@pytest.mark.asyncio
async def test_record_unknown_case_raises(session):
    p, s, tc, plan = await _fixture(session, "EX4")
    with pytest.raises(NotFound):
        await executions.record_execution(
            session,
            ExecutionCreate(case_id=99999, plan_id=plan.id, build_name="b", status="pass"),
            tester_id=None,
        )


@pytest.mark.asyncio
async def test_list_executions_for_case(session):
    p, s, tc, plan = await _fixture(session, "EX5")
    await executions.record_execution(
        session,
        ExecutionCreate(case_id=tc.id, plan_id=plan.id, build_name="b", status="pass"),
        tester_id=None,
    )
    rows = await executions.list_for_case(session, tc.id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_execution_endpoint(client, auth_headers, session):
    pc = await client.post(
        "/api/v1/projects", json={"name": "E", "prefix": "EXE"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    sc = await client.post(
        f"/api/v1/projects/{pid}/suites", json={"name": "S"}, headers=auth_headers
    )
    cc = await client.post(
        f"/api/v1/suites/{sc.json()['id']}/cases", json={"name": "c"}, headers=auth_headers
    )
    plan = TestPlan(project_id=pid, name="P")
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    resp = await client.post(
        "/api/v1/executions",
        json={"case_id": cc.json()["id"], "plan_id": plan.id, "build_name": "b1", "status": "pass"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pass"
