import pytest

from app import storage
from app.schemas.execution import ExecutionCreate
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import evidence, executions, plans, projects, suites, testcases


@pytest.fixture(autouse=True)
def _fake_storage(monkeypatch):
    monkeypatch.setattr(storage, "put_object", lambda key, data, ct: key)


async def _case_with_run(session, prefix, agent_id):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id,
            plan_id=plan.id,
            build_name="b",
            status="fail",
            claims=["claim A"],
        ),
        tester_id=agent_id,
    )
    return tc, ex


@pytest.mark.asyncio
async def test_get_execution_evidence_bundle(session, user):
    tc, ex = await _case_with_run(session, "EB1", user.id)
    await evidence.upload_artifact(session, ex.id, "log", "l", b"x", "text/plain")
    bundle = await evidence.get_execution_evidence(session, tc.id)
    assert bundle.case_id == tc.id
    assert len(bundle.executions) == 1
    e = bundle.executions[0]
    assert e.claims == ["claim A"]
    assert len(e.artifacts) == 1


@pytest.mark.asyncio
async def test_get_agent_execution_history(session, user):
    tc, ex = await _case_with_run(session, "EB2", user.id)
    rows = await evidence.get_agent_execution_history(session, user.id)
    assert len(rows) == 1
    assert rows[0].id == ex.id


@pytest.mark.asyncio
async def test_evidence_endpoint(client, auth_headers, session, user):
    tc, ex = await _case_with_run(session, "EBE", user.id)
    resp = await client.get(f"/api/v1/cases/{tc.id}/evidence", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["case_id"] == tc.id
