import datetime as dt

from pydantic import BaseModel


class StepResultIn(BaseModel):
    step_number: int
    status: str  # pass|fail|blocked|not_run
    notes: str | None = None


class ExecutionCreate(BaseModel):
    case_id: int | None = None
    external_id: str | None = None
    project_id: int | None = None  # required if external_id is used
    plan_id: int | None = None
    build_name: str
    commit_id: str | None = None
    status: str  # pass|fail|blocked|not_run|in_progress
    step_results: list[StepResultIn] = []
    notes: str | None = None
    duration: int | None = None
    session_id: str | None = None
    run_id: str | None = None
    claims: list[str] = []
    reasoning: dict | None = None
    agent_model: str | None = None


class ExecutionStepOut(BaseModel):
    step_id: int
    status: str
    notes: str | None = None

    model_config = {"from_attributes": True}


class ExecutionOut(BaseModel):
    id: int
    version_id: int
    build_id: int | None
    plan_id: int | None
    tester_id: int | None
    status: str
    notes: str | None = None
    duration: int | None = None
    session_id: str | None = None
    run_id: str | None = None
    created_at: dt.datetime
    steps: list[ExecutionStepOut] = []

    model_config = {"from_attributes": True}
