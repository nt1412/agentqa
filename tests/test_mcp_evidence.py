import pytest

from app import storage
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
    monkeypatch.setattr(storage, "put_object", lambda key, data, ct: key)


async def _case_plan(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="M", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    return tc, plan


@pytest.mark.asyncio
async def test_record_run_with_claims_then_evidence(session):
    tc, plan = await _case_plan(session, "MEV1")
    await mcp.record_test_run(
        case_id=tc.id,
        plan_id=plan.id,
        build_name="b",
        status="fail",
        claims=["x broke"],
        reasoning={"note": "stacktrace"},
    )
    ev = await mcp.get_execution_evidence(case_id=tc.id)
    assert ev["case_id"] == tc.id
    assert ev["executions"][0]["claims"] == ["x broke"]


@pytest.mark.asyncio
async def test_verify_claim_via_mcp(session, user):
    tc, plan = await _case_plan(session, "MEV2")
    await mcp.record_test_run(
        case_id=tc.id, plan_id=plan.id, build_name="b", status="pass", claims=["ok"]
    )
    unverified = await mcp.list_unverified_claims()
    assert len(unverified) >= 1
    cid = unverified[0]["id"]
    res = await mcp.verify_claim(claim_id=cid, verdict="confirmed", auditor_id=user.id)
    assert res["verdict"] == "confirmed"


@pytest.mark.asyncio
async def test_upload_artifact_via_mcp(session):
    tc, plan = await _case_plan(session, "MEV3")
    run = await mcp.record_test_run(case_id=tc.id, plan_id=plan.id, build_name="b", status="fail")
    art = await mcp.upload_artifact(
        execution_id=run["id"], artifact_type="log", title="t", content_base64="aGk="
    )
    assert art["artifact_type"] == "log"
