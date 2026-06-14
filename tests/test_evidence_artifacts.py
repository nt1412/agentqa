import pytest
from sqlalchemy import select

from app import storage
from app.models.evidence import ExecutionArtifact
from app.schemas.execution import ExecutionCreate
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import evidence, executions, plans, projects, suites, testcases


@pytest.fixture(autouse=True)
def _fake_storage(monkeypatch):
    saved = {}

    def fake_put(key, data, content_type):
        saved[key] = (data, content_type)
        return key

    monkeypatch.setattr(storage, "put_object", fake_put)
    return saved


async def _execution(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    return await executions.record_execution(
        session,
        ExecutionCreate(case_id=tc.id, plan_id=plan.id, build_name="b", status="fail"),
        tester_id=None,
    )


@pytest.mark.asyncio
async def test_upload_artifact_stores_blob_and_row(session, _fake_storage):
    ex = await _execution(session, "AR1")
    art = await evidence.upload_artifact(
        session,
        ex.id,
        artifact_type="log",
        title="run log",
        content=b"trace bytes",
        mime_type="text/plain",
    )
    assert art.id is not None
    assert art.blob_key.startswith(f"exec/{ex.id}/log/")
    assert art.size == len(b"trace bytes")
    # blob was handed to storage
    assert _fake_storage[art.blob_key][0] == b"trace bytes"
    # row persisted
    rows = (
        (
            await session.execute(
                select(ExecutionArtifact).where(ExecutionArtifact.execution_id == ex.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_list_artifacts(session, _fake_storage):
    ex = await _execution(session, "AR2")
    await evidence.upload_artifact(session, ex.id, "log", "a", b"x", "text/plain")
    await evidence.upload_artifact(session, ex.id, "screenshot", "b", b"y", "image/png")
    rows = await evidence.list_artifacts(session, ex.id)
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_upload_artifact_endpoint(client, auth_headers, session, _fake_storage):
    ex = await _execution(session, "ARE")
    resp = await client.post(
        f"/api/v1/executions/{ex.id}/artifacts",
        json={
            "artifact_type": "log",
            "title": "t",
            "content": "aGVsbG8=",
            "mime_type": "text/plain",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["artifact_type"] == "log"
