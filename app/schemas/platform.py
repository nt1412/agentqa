from pydantic import BaseModel


class PlatformCreate(BaseModel):
    name: str
    notes: str | None = None


class PlatformOut(BaseModel):
    id: int
    project_id: int
    name: str
    notes: str | None = None
    active: bool

    model_config = {"from_attributes": True}
