from fastapi import APIRouter, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.services import reruns

router = APIRouter(prefix="/api/v1", tags=["reruns"])


class RerunRequest(BaseModel):
    assignee_id: int
    case_id: int | None = None  # omit to re-run every case in the build's plan
    assignee_type: str = "agent"


@router.post("/builds/{build_id}/rerun", status_code=status.HTTP_201_CREATED)
async def request_rerun(
    build_id: int, body: RerunRequest, session: SessionDep, user: CurrentUser
):
    """Request a re-run of a case (or the whole build) — created as 'rerun'
    assignments the assignee discovers via the shared work queue. Idempotent."""
    created = await reruns.request_rerun(
        session,
        build_id=build_id,
        assignee_id=body.assignee_id,
        assigner_id=user.id,
        case_id=body.case_id,
        assignee_type=body.assignee_type,
    )
    return [
        {"id": a.id, "case_id": a.case_id, "build_id": a.build_id, "status": a.status}
        for a in created
    ]
