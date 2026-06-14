from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.requirement import (
    ReqSpecCreate,
    ReqSpecOut,
    RequirementCreate,
    RequirementOut,
)
from app.services import requirements

router = APIRouter(prefix="/api/v1", tags=["requirements"])


@router.post(
    "/projects/{project_id}/req-specs",
    response_model=ReqSpecOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_spec(project_id: int, body: ReqSpecCreate, session: SessionDep, user: CurrentUser):
    return await requirements.create_req_spec(session, project_id, body)


@router.get("/projects/{project_id}/req-specs", response_model=list[ReqSpecOut])
async def list_specs(project_id: int, session: SessionDep, user: CurrentUser):
    return await requirements.list_req_specs(session, project_id)


@router.post(
    "/req-specs/{spec_id}/requirements",
    response_model=RequirementOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_req(spec_id: int, body: RequirementCreate, session: SessionDep, user: CurrentUser):
    return await requirements.create_requirement(session, spec_id, body)


@router.get("/req-specs/{spec_id}/requirements", response_model=list[RequirementOut])
async def list_reqs(spec_id: int, session: SessionDep, user: CurrentUser):
    reqs = await requirements.list_requirements(session, spec_id)
    return [await requirements.get_requirement(session, r.id) for r in reqs]
