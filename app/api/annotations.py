from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.annotation import AnnotationCreate, AnnotationOut
from app.services import annotations

router = APIRouter(prefix="/api/v1", tags=["annotations"])


@router.post("/annotations", response_model=AnnotationOut, status_code=status.HTTP_201_CREATED)
async def create(body: AnnotationCreate, session: SessionDep, user: CurrentUser):
    """Attach a note to any entity (regression / case / build). Author is the caller."""
    return await annotations.create_annotation(
        session, body.entity_type, body.entity_id, body.text, user.id
    )


@router.get("/annotations", response_model=list[AnnotationOut])
async def list_for_entity(
    entity_type: str, entity_id: int, session: SessionDep, user: CurrentUser
):
    return await annotations.list_annotations(session, entity_type, entity_id)
