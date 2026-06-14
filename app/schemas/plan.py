from pydantic import BaseModel


class PlanCreate(BaseModel):
    name: str
    notes: str | None = None


class PlanUpdate(BaseModel):
    name: str | None = None
    notes: str | None = None
    active: bool | None = None
    is_open: bool | None = None


class PlanOut(BaseModel):
    id: int
    project_id: int
    name: str
    notes: str | None = None
    active: bool
    is_open: bool

    model_config = {"from_attributes": True}
