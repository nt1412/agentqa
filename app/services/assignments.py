from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Assignment
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate
from app.services.errors import NotFound


async def create_assignment(
    session: AsyncSession, data: AssignmentCreate, assigner_id: int | None
) -> Assignment:
    assignment = Assignment(
        case_id=data.case_id,
        plan_id=data.plan_id,
        build_id=data.build_id,
        assignee_id=data.assignee_id,
        assignee_type=data.assignee_type,
        deadline=data.deadline,
        status="open",
        assigner_id=assigner_id,
    )
    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment


async def get_assignment(session: AsyncSession, assignment_id: int) -> Assignment:
    assignment = await session.get(Assignment, assignment_id)
    if assignment is None:
        raise NotFound(f"assignment {assignment_id} not found")
    return assignment


async def list_assignments(
    session: AsyncSession,
    plan_id: int | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
) -> list[Assignment]:
    stmt = select(Assignment)
    if plan_id is not None:
        stmt = stmt.where(Assignment.plan_id == plan_id)
    if assignee_id is not None:
        stmt = stmt.where(Assignment.assignee_id == assignee_id)
    if status is not None:
        stmt = stmt.where(Assignment.status == status)
    stmt = stmt.order_by(Assignment.id)
    return list((await session.execute(stmt)).scalars().all())


async def update_assignment(
    session: AsyncSession, assignment_id: int, data: AssignmentUpdate
) -> Assignment:
    assignment = await get_assignment(session, assignment_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(assignment, field, value)
    await session.commit()
    await session.refresh(assignment)
    return assignment
