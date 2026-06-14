import datetime as dt

from pydantic import BaseModel


class AssignmentCreate(BaseModel):
    case_id: int
    plan_id: int
    build_id: int | None = None
    assignee_id: int
    assignee_type: str  # human|agent
    deadline: dt.datetime | None = None


class AssignmentUpdate(BaseModel):
    status: str | None = None
    deadline: dt.datetime | None = None


class AssignmentOut(BaseModel):
    id: int
    case_id: int
    plan_id: int
    build_id: int | None
    assignee_id: int
    assignee_type: str
    deadline: dt.datetime | None = None
    status: str
    assigner_id: int | None = None

    model_config = {"from_attributes": True}
