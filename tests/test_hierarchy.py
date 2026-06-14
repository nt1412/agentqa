import pytest

from app.models.plan import TestPlan
from app.schemas.execution import ExecutionCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import executions, plans, projects, suites, testcases
from app.services.errors import NotFound, ValidationFailed


async def _project_with_cases(session, prefix, n=3):
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
    return p, suite, cases, plan


# ---------- dependencies ----------


@pytest.mark.asyncio
async def test_add_and_get_dependency(session):
    _, _, cases, _ = await _project_with_cases(session, "DEP1")
    await testcases.add_dependency(session, cases[1].id, cases[0].id)
    assert await testcases.get_dependencies(session, cases[1].id) == [cases[0].id]
    assert await testcases.get_dependencies(session, cases[0].id) == []


@pytest.mark.asyncio
async def test_dependency_is_idempotent(session):
    _, _, cases, _ = await _project_with_cases(session, "DEP2")
    await testcases.add_dependency(session, cases[1].id, cases[0].id)
    await testcases.add_dependency(session, cases[1].id, cases[0].id)
    assert await testcases.get_dependencies(session, cases[1].id) == [cases[0].id]


@pytest.mark.asyncio
async def test_dependency_rejects_self(session):
    _, _, cases, _ = await _project_with_cases(session, "DEP3")
    with pytest.raises(ValidationFailed):
        await testcases.add_dependency(session, cases[0].id, cases[0].id)


@pytest.mark.asyncio
async def test_dependency_rejects_cycle(session):
    _, _, cases, _ = await _project_with_cases(session, "DEP4")
    await testcases.add_dependency(session, cases[1].id, cases[0].id)
    await testcases.add_dependency(session, cases[2].id, cases[1].id)
    # cases[0] depending on cases[2] would close the loop 0->2->1->0
    with pytest.raises(ValidationFailed):
        await testcases.add_dependency(session, cases[0].id, cases[2].id)


@pytest.mark.asyncio
async def test_dependency_rejects_cross_project(session):
    _, _, cases_a, _ = await _project_with_cases(session, "DEP5A", n=1)
    _, _, cases_b, _ = await _project_with_cases(session, "DEP5B", n=1)
    with pytest.raises(ValidationFailed):
        await testcases.add_dependency(session, cases_a[0].id, cases_b[0].id)


@pytest.mark.asyncio
async def test_dependency_unknown_case(session):
    _, _, cases, _ = await _project_with_cases(session, "DEP6", n=1)
    with pytest.raises(NotFound):
        await testcases.add_dependency(session, cases[0].id, 999999)


# ---------- suite tree ----------


@pytest.mark.asyncio
async def test_suite_tree_and_counts(session):
    p = await projects.create_project(session, ProjectCreate(name="T", prefix="TREE"))
    parent = await suites.create_suite(session, p.id, SuiteCreate(name="Parent"))
    child = await suites.create_suite(
        session, p.id, SuiteCreate(name="Child", parent_id=parent.id)
    )
    await testcases.create_test_case(session, child.id, TestCaseCreate(name="x"))
    tree = await suites.get_tree(session, p.id)
    counts = await suites.case_counts(session, p.id)
    assert len(tree) == 1
    assert tree[0].id == parent.id
    assert tree[0].children[0].id == child.id
    assert counts[child.id] == 1
    assert counts.get(parent.id, 0) == 0


# ---------- run manifest + gating ----------


@pytest.mark.asyncio
async def test_run_manifest_orders_and_includes_priority(session):
    _, _, cases, plan = await _project_with_cases(session, "MAN1")
    await plans.add_cases(session, plan.id, [c.id for c in cases], urgency=3)
    manifest = await plans.get_run_manifest(session, plan.id)
    assert [m["case_id"] for m in manifest] == [c.id for c in cases]
    assert [m["order"] for m in manifest] == [1, 2, 3]
    assert all(m["urgency"] == 3 for m in manifest)
    assert all(m["latest_status"] == "not_run" for m in manifest)
    assert all(m["runnable"] for m in manifest)


@pytest.mark.asyncio
async def test_run_manifest_gating(session):
    _, _, cases, plan = await _project_with_cases(session, "MAN2")
    # case[1] depends on case[0]
    await plans.add_cases(session, plan.id, [cases[0].id, cases[1].id])
    await testcases.add_dependency(session, cases[1].id, cases[0].id)

    # prerequisite not yet run → dependent is blocked
    manifest = {m["case_id"]: m for m in await plans.get_run_manifest(session, plan.id)}
    assert manifest[cases[1].id]["depends_on"] == [cases[0].id]
    assert manifest[cases[1].id]["blocked_by"] == [cases[0].id]
    assert manifest[cases[1].id]["runnable"] is False

    # prerequisite passes → dependent unblocks
    await executions.record_execution(
        session,
        ExecutionCreate(case_id=cases[0].id, plan_id=plan.id, build_name="b1", status="pass"),
        tester_id=None,
    )
    manifest = {m["case_id"]: m for m in await plans.get_run_manifest(session, plan.id)}
    assert manifest[cases[1].id]["blocked_by"] == []
    assert manifest[cases[1].id]["runnable"] is True
    assert manifest[cases[0].id]["latest_status"] == "pass"


@pytest.mark.asyncio
async def test_latest_status_breaks_ties_by_id(session):
    from sqlalchemy import update

    from app.models.execution import Execution

    _, _, cases, plan = await _project_with_cases(session, "MAN4")
    await plans.add_cases(session, plan.id, [cases[0].id, cases[1].id])
    await testcases.add_dependency(session, cases[1].id, cases[0].id)

    e1 = await executions.record_execution(
        session,
        ExecutionCreate(case_id=cases[0].id, plan_id=plan.id, build_name="b1", status="pass"),
        tester_id=None,
    )
    e2 = await executions.record_execution(
        session,
        ExecutionCreate(case_id=cases[0].id, plan_id=plan.id, build_name="b1", status="fail"),
        tester_id=None,
    )
    # force identical created_at so only the id tiebreak can decide "latest"
    same = (await session.get(Execution, e1.id)).created_at
    await session.execute(
        update(Execution).where(Execution.id.in_([e1.id, e2.id])).values(created_at=same)
    )
    await session.commit()

    manifest = {m["case_id"]: m for m in await plans.get_run_manifest(session, plan.id)}
    # higher-id execution (fail) wins the tie → prereq not passing → dependent blocked
    assert manifest[cases[0].id]["latest_status"] == "fail"
    assert manifest[cases[1].id]["runnable"] is False


@pytest.mark.asyncio
async def test_run_manifest_gating_stays_blocked_on_fail(session):
    _, _, cases, plan = await _project_with_cases(session, "MAN3")
    await plans.add_cases(session, plan.id, [cases[0].id, cases[1].id])
    await testcases.add_dependency(session, cases[1].id, cases[0].id)
    await executions.record_execution(
        session,
        ExecutionCreate(case_id=cases[0].id, plan_id=plan.id, build_name="b1", status="fail"),
        tester_id=None,
    )
    manifest = {m["case_id"]: m for m in await plans.get_run_manifest(session, plan.id)}
    assert manifest[cases[1].id]["runnable"] is False
