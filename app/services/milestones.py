from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Milestone
from app.schemas.plan import MilestoneCreate
from app.services.plans import get_plan


async def create_milestone(session: AsyncSession, plan_id: int, data: MilestoneCreate) -> Milestone:
    await get_plan(session, plan_id)  # raises NotFound if absent
    milestone = Milestone(
        plan_id=plan_id,
        name=data.name,
        target_date=data.target_date,
        start_date=data.start_date,
    )
    session.add(milestone)
    await session.commit()
    await session.refresh(milestone)
    return milestone


async def list_milestones(session: AsyncSession, plan_id: int) -> list[Milestone]:
    stmt = select(Milestone).where(Milestone.plan_id == plan_id).order_by(Milestone.id)
    return list((await session.execute(stmt)).scalars().all())
