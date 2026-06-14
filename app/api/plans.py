from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.plan import PlanCreate, PlanOut, PlanUpdate
from app.services import plans

router = APIRouter(prefix="/api/v1", tags=["plans"])


@router.post(
    "/projects/{project_id}/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED
)
async def create(project_id: int, body: PlanCreate, session: SessionDep, user: CurrentUser):
    return await plans.create_plan(session, project_id, body)


@router.get("/projects/{project_id}/plans", response_model=list[PlanOut])
async def list_all(project_id: int, session: SessionDep, user: CurrentUser):
    return await plans.list_plans(session, project_id)


@router.get("/plans/{plan_id}", response_model=PlanOut)
async def get_one(plan_id: int, session: SessionDep, user: CurrentUser):
    return await plans.get_plan(session, plan_id)


@router.put("/plans/{plan_id}", response_model=PlanOut)
async def update(plan_id: int, body: PlanUpdate, session: SessionDep, user: CurrentUser):
    return await plans.update_plan(session, plan_id, body)
