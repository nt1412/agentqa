from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.platform import PlatformCreate, PlatformOut
from app.services import platforms

router = APIRouter(prefix="/api/v1", tags=["platforms"])


@router.post(
    "/projects/{project_id}/platforms",
    response_model=PlatformOut,
    status_code=status.HTTP_201_CREATED,
)
async def create(project_id: int, body: PlatformCreate, session: SessionDep, user: CurrentUser):
    return await platforms.create_platform(session, project_id, body)


@router.get("/projects/{project_id}/platforms", response_model=list[PlatformOut])
async def list_all(project_id: int, session: SessionDep, user: CurrentUser):
    return await platforms.list_platforms(session, project_id)
