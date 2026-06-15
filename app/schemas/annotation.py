import datetime as dt

from pydantic import BaseModel


class AnnotationCreate(BaseModel):
    entity_type: str
    entity_id: int
    text: str


class AnnotationOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    author_id: int | None = None
    text: str
    created_at: dt.datetime

    model_config = {"from_attributes": True}
