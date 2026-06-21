import pytest

from app import embeddings as emb_mod
from app import storage
from app.schemas.execution import ExecutionCreate, StepResultIn
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import StepIn, TestCaseCreate
from app.services import evidence, executions, plans, projects, suites, testcases
from app.services.errors import NotFound
from tests._embed_helpers import fake_embed


@pytest.fixture(autouse=True)
def _fakes(monkeypatch):
    monkeypatch.setattr(emb_mod, "is_available", lambda: True)
    monkeypatch.setattr(emb_mod, "embed", fake_embed)
    monkeypatch.setattr(storage, "put_object", lambda key, data, ct: key)


@pytest.mark.asyncio
async def test_failure_context_bundle(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="FC1"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(
        session, s.id, TestCaseCreate(name="login", steps=[StepIn(action="submit")])
    )
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id,
            plan_id=plan.id,
            build_name="b",
            status="fail",
            notes="auth blew up",
            reasoning={"trace": "NPE"},
            step_results=[StepResultIn(step_number=1, status="fail", notes="500")],
        ),
        tester_id=None,
    )
    await evidence.upload_artifact(session, ex.id, "log", "l", b"x", "text/plain")

    ctx = await evidence.get_failure_context(session, tc.id)
    assert ctx.case_id == tc.id
    assert ctx.case_name == "login"
    assert len(ctx.recent_executions) == 1
    assert ctx.recent_executions[0].step_failures[0].status == "fail"
    assert ctx.prior_reasoning == [{"trace": "NPE"}]
    assert len(ctx.artifacts) == 1


@pytest.mark.asyncio
async def test_failure_context_surfaces_last_green_reasoning(session):
    # Phase 2: the last passing run's reasoning ("why it was green" — often the
    # fix for the issue now recurring) must surface even when buried under more
    # recent failures than the prior_reasoning recency cap (last_n).
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="FC3"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    green = {"root_cause": "UseBlacklist=0 closes the shared self-DoS"}
    await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id, plan_id=plan.id, build_name="g", status="pass", reasoning=green
        ),
        tester_id=None,
    )
    for i in range(6):  # 6 newer failures > default last_n=5, burying the green note
        await executions.record_execution(
            session,
            ExecutionCreate(
                case_id=tc.id,
                plan_id=plan.id,
                build_name=f"f{i}",
                status="fail",
                reasoning={"root_cause": f"later unrelated failure {i}"},
            ),
            tester_id=None,
        )
    ctx = await evidence.get_failure_context(session, tc.id)
    assert ctx.last_green_reasoning == green


@pytest.mark.asyncio
async def test_failure_context_no_green_history(session):
    # never-green case: last_green_reasoning is None, not an error
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="FC4"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id, plan_id=plan.id, build_name="b", status="fail",
            reasoning={"root_cause": "first failure"},
        ),
        tester_id=None,
    )
    ctx = await evidence.get_failure_context(session, tc.id)
    assert ctx.last_green_reasoning is None


@pytest.mark.asyncio
async def test_failure_context_unknown_case(session):
    with pytest.raises(NotFound):
        await evidence.get_failure_context(session, 999999)


@pytest.mark.asyncio
async def test_failure_context_excludes_passing_executions(session):
    # Regression (Phase 2c review I-1): recent_executions must contain only failures.
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="FC2"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    await executions.record_execution(
        session,
        ExecutionCreate(case_id=tc.id, plan_id=plan.id, build_name="b", status="pass", notes="ok"),
        tester_id=None,
    )
    await executions.record_execution(
        session,
        ExecutionCreate(case_id=tc.id, plan_id=plan.id, build_name="b", status="fail", notes="bad"),
        tester_id=None,
    )
    ctx = await evidence.get_failure_context(session, tc.id)
    assert len(ctx.recent_executions) == 1
    assert ctx.recent_executions[0].status == "fail"
