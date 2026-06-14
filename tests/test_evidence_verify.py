import pytest

from app.schemas.evidence import VerificationCreate
from app.schemas.execution import ExecutionCreate
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import evidence, executions, plans, projects, suites, testcases
from app.services.errors import NotFound


async def _execution_with_claim(session, prefix):
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
            status="pass",
            claims=["it works"],
        ),
        tester_id=None,
    )
    return ex


@pytest.mark.asyncio
async def test_unverified_then_verified(session, user):
    await _execution_with_claim(session, "VF1")
    unverified = await evidence.list_unverified_claims(session)
    assert len(unverified) == 1
    claim_id = unverified[0].id

    v = await evidence.verify_claim(
        session,
        claim_id,
        VerificationCreate(verdict="confirmed", reasoning={"why": "checked"}),
        auditor_id=user.id,
    )
    assert v.verdict == "confirmed"
    # claim no longer appears as unverified
    assert await evidence.list_unverified_claims(session) == []


@pytest.mark.asyncio
async def test_multiple_auditors_per_claim(session, user):
    await _execution_with_claim(session, "VF2")
    claim_id = (await evidence.list_unverified_claims(session))[0].id
    await evidence.verify_claim(
        session, claim_id, VerificationCreate(verdict="confirmed"), auditor_id=user.id
    )
    await evidence.verify_claim(
        session, claim_id, VerificationCreate(verdict="refuted"), auditor_id=user.id
    )
    verifications = await evidence.list_verifications(session, claim_id)
    assert {v.verdict for v in verifications} == {"confirmed", "refuted"}


@pytest.mark.asyncio
async def test_verify_unknown_claim_raises(session, user):
    with pytest.raises(NotFound):
        await evidence.verify_claim(
            session, 999999, VerificationCreate(verdict="confirmed"), auditor_id=user.id
        )


@pytest.mark.asyncio
async def test_verify_endpoint(client, auth_headers, session, user):
    await _execution_with_claim(session, "VFE")
    unv = await client.get("/api/v1/claims/unverified", headers=auth_headers)
    assert unv.status_code == 200
    claim_id = unv.json()[0]["id"]
    resp = await client.post(
        f"/api/v1/claims/{claim_id}/verify",
        json={"verdict": "confirmed"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["verdict"] == "confirmed"
