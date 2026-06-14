from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.execution import ExecutionCreate, ExecutionOut
from app.services import executions

router = APIRouter(prefix="/api/v1", tags=["executions"])


@router.post("/executions", response_model=ExecutionOut, status_code=status.HTTP_201_CREATED)
async def record(
    body: ExecutionCreate, session: SessionDep, user: CurrentUser, cascade: bool = False
):
    """Record an execution. Pass ?cascade=true to auto-block downstream cases
    (dependents in the same plan) when this run fails/blocks."""
    tester_id = None if user.auth_method == "agent" else user.id
    return await executions.record_execution(session, body, tester_id=tester_id, cascade=cascade)


@router.get("/executions/{execution_id}", response_model=ExecutionOut)
async def get_one(execution_id: int, session: SessionDep, user: CurrentUser):
    return await executions.get_execution(session, execution_id)


@router.get("/cases/{case_id}/executions", response_model=list[ExecutionOut])
async def for_case(case_id: int, session: SessionDep, user: CurrentUser):
    return await executions.list_for_case(session, case_id)


@router.get("/plans/{plan_id}/executions", response_model=list[ExecutionOut])
async def for_plan(plan_id: int, session: SessionDep, user: CurrentUser):
    return await executions.list_for_plan(session, plan_id)
