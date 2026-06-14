from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.assignment import AssignmentCreate, AssignmentOut, AssignmentUpdate
from app.services import assignments

router = APIRouter(prefix="/api/v1/assignments", tags=["assignments"])


@router.post("", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def create(body: AssignmentCreate, session: SessionDep, user: CurrentUser):
    return await assignments.create_assignment(session, body, assigner_id=user.id)


@router.get("", response_model=list[AssignmentOut])
async def list_all(
    session: SessionDep,
    user: CurrentUser,
    plan_id: int | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
):
    return await assignments.list_assignments(session, plan_id, assignee_id, status)


@router.put("/{assignment_id}", response_model=AssignmentOut)
async def update(
    assignment_id: int, body: AssignmentUpdate, session: SessionDep, user: CurrentUser
):
    return await assignments.update_assignment(session, assignment_id, body)
