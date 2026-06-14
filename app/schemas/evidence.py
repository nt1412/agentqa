from pydantic import BaseModel


class ArtifactOut(BaseModel):
    id: int
    execution_id: int
    artifact_type: str
    title: str | None = None
    blob_key: str
    size: int | None = None
    mime_type: str | None = None

    model_config = {"from_attributes": True}
