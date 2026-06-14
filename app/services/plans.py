from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import TestPlan
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
