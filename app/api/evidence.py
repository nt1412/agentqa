import base64

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.schemas.evidence import ArtifactOut
from app.services import evidence

router = APIRouter(prefix="/api/v1", tags=["evidence"])


class _ArtifactIn(BaseModel):
    artifact_type: str
    title: str | None = None
    content: str  # base64-encoded bytes
    mime_type: str | None = None


@router.post(
    "/executions/{execution_id}/artifacts",
    response_model=ArtifactOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_artifact(
    execution_id: int, body: _ArtifactIn, session: SessionDep, user: CurrentUser
):
    content = base64.b64decode(body.content)
    return await evidence.upload_artifact(
        session, execution_id, body.artifact_type, body.title, content, body.mime_type
    )


@router.get("/executions/{execution_id}/artifacts", response_model=list[ArtifactOut])
async def list_artifacts(execution_id: int, session: SessionDep, user: CurrentUser):
    return await evidence.list_artifacts(session, execution_id)
