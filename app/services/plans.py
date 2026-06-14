from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import Execution
from app.models.plan import TestPlan, TestPlanCase
from app.models.testcase import TestCase, TestCaseVersion
from app.schemas.plan import PlanCreate, PlanUpdate
from app.services.errors import NotFound
from app.services.projects import get_project
from app.services.testcases import get_dependencies


async def create_plan(session: AsyncSession, project_id: int, data: PlanCreate) -> TestPlan:
    await get_project(session, project_id)
    plan = TestPlan(project_id=project_id, name=data.name, notes=data.notes)
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return plan


async def get_plan(session: AsyncSession, plan_id: int) -> TestPlan:
    plan = await session.get(TestPlan, plan_id)
    if plan is None:
        raise NotFound(f"test plan {plan_id} not found")
    return plan


async def list_plans(session: AsyncSession, project_id: int) -> list[TestPlan]:
    stmt = select(TestPlan).where(TestPlan.project_id == project_id).order_by(TestPlan.id)
    return list((await session.execute(stmt)).scalars().all())


async def update_plan(session: AsyncSession, plan_id: int, data: PlanUpdate) -> TestPlan:
    plan = await get_plan(session, plan_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await session.commit()
    await session.refresh(plan)
    return plan


async def _current_version_id(session: AsyncSession, case_id: int) -> int:
    stmt = (
        select(TestCaseVersion)
        .where(TestCaseVersion.case_id == case_id, TestCaseVersion.active.is_(True))
        .order_by(TestCaseVersion.version.desc())
    )
    v = (await session.execute(stmt)).scalars().first()
    if v is None:
        raise NotFound(f"test case {case_id} has no active version")
    return v.id


async def add_cases(
    session: AsyncSession,
    plan_id: int,
    case_ids: list[int],
    platform_id: int | None = None,
    urgency: int = 2,
) -> list[TestPlanCase]:
    await get_plan(session, plan_id)
    next_order = (
        await session.execute(
            select(func.coalesce(func.max(TestPlanCase.order), 0)).where(
                TestPlanCase.plan_id == plan_id
            )
        )
    ).scalar_one() + 1
    created: list[TestPlanCase] = []
    for case_id in case_ids:
        version_id = await _current_version_id(session, case_id)
        existing = (
            await session.execute(
                select(TestPlanCase).where(
                    TestPlanCase.plan_id == plan_id,
                    TestPlanCase.version_id == version_id,
                    TestPlanCase.platform_id.is_(platform_id)
                    if platform_id is None
                    else TestPlanCase.platform_id == platform_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            created.append(existing)
            continue
        link = TestPlanCase(
            plan_id=plan_id,
            version_id=version_id,
            platform_id=platform_id,
            urgency=urgency,
            order=next_order,
        )
        next_order += 1
        session.add(link)
        await session.flush()
        created.append(link)
    await session.commit()
    return created


async def list_plan_cases(session: AsyncSession, plan_id: int) -> list[TestPlanCase]:
    stmt = select(TestPlanCase).where(TestPlanCase.plan_id == plan_id).order_by(TestPlanCase.id)
    return list((await session.execute(stmt)).scalars().all())


async def remove_case(session: AsyncSession, plan_id: int, case_id: int) -> None:
    # Version-agnostic: "remove this case from the plan" must drop links to ANY of
    # the case's versions, not just the current active one — otherwise a case linked
    # under v1 and later bumped to v2 leaves an orphaned v1 link (skews coverage).
    version_ids = (
        (
            await session.execute(
                select(TestCaseVersion.id).where(TestCaseVersion.case_id == case_id)
            )
        )
        .scalars()
        .all()
    )
    if not version_ids:
        return
    stmt = select(TestPlanCase).where(
        TestPlanCase.plan_id == plan_id, TestPlanCase.version_id.in_(version_ids)
    )
    for link in (await session.execute(stmt)).scalars().all():
        await session.delete(link)
    await session.commit()


async def _latest_status_by_case(
    session: AsyncSession, case_ids: list[int], build_id: int | None = None
) -> dict[int, str]:
    """Most recent execution status for each case (across all its versions).

    When build_id is given, only executions for that build count — so gating
    asks "did this prerequisite pass *in this build*?" (regression semantics)
    rather than "did it ever pass anywhere".
    """
    if not case_ids:
        return {}
    stmt = (
        select(TestCase.id, Execution.status, Execution.created_at)
        .join(TestCaseVersion, TestCaseVersion.case_id == TestCase.id)
        .join(Execution, Execution.version_id == TestCaseVersion.id)
        .where(TestCase.id.in_(case_ids))
        # id breaks ties when executions share a created_at (bulk-recorded
        # in the same second) — otherwise "latest" is nondeterministic.
        .order_by(Execution.created_at.desc(), Execution.id.desc())
    )
    if build_id is not None:
        stmt = stmt.where(Execution.build_id == build_id)
    rows = (await session.execute(stmt)).all()
    latest: dict[int, str] = {}
    for cid, status, _created in rows:
        if cid not in latest:  # rows are newest-first, so first seen wins
            latest[cid] = status
    return latest


async def get_run_manifest(
    session: AsyncSession, plan_id: int, build_id: int | None = None
) -> list[dict]:
    """The ordered, priority- and dependency-aware run list for a plan.

    Each entry tells an agent what to run, in what order, at what priority, and
    whether prerequisites are satisfied:
      order, urgency, case_id, external_id, name, importance, latest_status,
      depends_on (prerequisite case ids), blocked_by (prereqs not yet passing),
      runnable (bool — true iff blocked_by is empty).

    Pass build_id to gate against that build only (regression: a prerequisite
    that passed in an older build does not count). Default is global-latest.
    """
    await get_plan(session, plan_id)
    links = (
        (
            await session.execute(
                select(TestPlanCase)
                .where(TestPlanCase.plan_id == plan_id)
                .order_by(TestPlanCase.order, TestPlanCase.id)
            )
        )
        .scalars()
        .all()
    )
    if not links:
        return []

    version_ids = [link.version_id for link in links]
    vrows = (
        await session.execute(
            select(
                TestCaseVersion.id, TestCaseVersion.case_id, TestCaseVersion.importance
            ).where(TestCaseVersion.id.in_(version_ids))
        )
    ).all()
    vmap = {vid: (cid, imp) for vid, cid, imp in vrows}
    case_ids = [vmap[vid][0] for vid in version_ids if vid in vmap]

    crows = (
        await session.execute(
            select(TestCase.id, TestCase.external_id, TestCase.name).where(
                TestCase.id.in_(case_ids)
            )
        )
    ).all()
    cmeta = {cid: (ext, name) for cid, ext, name in crows}

    # resolve dependencies up front; include prerequisites that aren't in the
    # plan so their status is still evaluated (otherwise an out-of-plan prereq
    # would always read as "not passing").
    deps_by_case = {cid: await get_dependencies(session, cid) for cid in set(case_ids)}
    status_ids = set(case_ids) | {d for deps in deps_by_case.values() for d in deps}
    latest = await _latest_status_by_case(session, list(status_ids), build_id)

    manifest: list[dict] = []
    for link in links:
        cid, importance = vmap.get(link.version_id, (None, None))
        if cid is None:
            continue
        ext, name = cmeta.get(cid, (None, None))
        deps = deps_by_case.get(cid, [])
        blocked_by = [d for d in deps if latest.get(d) != "pass"]
        manifest.append(
            {
                "order": link.order,
                "urgency": link.urgency,
                "case_id": cid,
                "external_id": ext,
                "name": name,
                "importance": importance,
                "latest_status": latest.get(cid, "not_run"),
                "depends_on": deps,
                "blocked_by": blocked_by,
                "runnable": len(blocked_by) == 0,
            }
        )
    return manifest
