from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import TestPlan, TestPlanCase
from app.models.testcase import TestCaseVersion
from app.schemas.plan import PlanCreate, PlanUpdate
from app.services.errors import NotFound
from app.services.projects import get_project


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
            plan_id=plan_id, version_id=version_id, platform_id=platform_id, urgency=urgency
        )
        session.add(link)
        await session.flush()
        created.append(link)
    await session.commit()
    return created


async def list_plan_cases(session: AsyncSession, plan_id: int) -> list[TestPlanCase]:
    stmt = select(TestPlanCase).where(TestPlanCase.plan_id == plan_id).order_by(TestPlanCase.id)
    return list((await session.execute(stmt)).scalars().all())


async def remove_case(session: AsyncSession, plan_id: int, case_id: int) -> None:
    version_id = await _current_version_id(session, case_id)
    stmt = select(TestPlanCase).where(
        TestPlanCase.plan_id == plan_id, TestPlanCase.version_id == version_id
    )
    for link in (await session.execute(stmt)).scalars().all():
        await session.delete(link)
    await session.commit()
