from pydantic import BaseModel


class SuiteCreate(BaseModel):
    name: str
    parent_id: int | None = None
    details: str | None = None


class SuiteOut(BaseModel):
    id: int
    project_id: int
    parent_id: int | None
    name: str
    details: str | None = None
    order: int

    model_config = {"from_attributes": True}


class SuiteNode(SuiteOut):
    children: list["SuiteNode"] = []
