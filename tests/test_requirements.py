import pytest

from app.schemas.project import ProjectCreate
from app.schemas.requirement import ReqSpecCreate, RequirementCreate
from app.services import projects, requirements
from app.services.errors import NotFound


async def _spec(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    spec = await requirements.create_req_spec(
        session, p.id, ReqSpecCreate(doc_id="SRS-1", name="Login Spec")
    )
    return p, spec


@pytest.mark.asyncio
async def test_create_spec_and_requirement(session):
    p, spec = await _spec(session, "RQ1")
    assert spec.id is not None
    req = await requirements.create_requirement(
        session, spec.id, RequirementCreate(req_doc_id="REQ-1", name="rejects bad password")
    )
    assert req.id is not None
    full = await requirements.get_requirement(session, req.id)
    assert full.current_version.version == 1
    assert full.name == "rejects bad password"


@pytest.mark.asyncio
async def test_create_spec_unknown_project(session):
    with pytest.raises(NotFound):
        await requirements.create_req_spec(session, 9999, ReqSpecCreate(doc_id="X", name="x"))


@pytest.mark.asyncio
async def test_list_requirements(session):
    p, spec = await _spec(session, "RQ2")
    await requirements.create_requirement(
        session, spec.id, RequirementCreate(req_doc_id="REQ-1", name="a")
    )
    await requirements.create_requirement(
        session, spec.id, RequirementCreate(req_doc_id="REQ-2", name="b")
    )
    rows = await requirements.list_requirements(session, spec.id)
    assert {r.name for r in rows} == {"a", "b"}


@pytest.mark.asyncio
async def test_requirement_endpoints(client, auth_headers):
    pc = await client.post(
        "/api/v1/projects", json={"name": "P", "prefix": "RQE"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    sc = await client.post(
        f"/api/v1/projects/{pid}/req-specs",
        json={"doc_id": "SRS-1", "name": "Spec"},
        headers=auth_headers,
    )
    assert sc.status_code == 201
    spec_id = sc.json()["id"]
    rc = await client.post(
        f"/api/v1/req-specs/{spec_id}/requirements",
        json={"req_doc_id": "REQ-1", "name": "req one"},
        headers=auth_headers,
    )
    assert rc.status_code == 201
    assert rc.json()["current_version"]["version"] == 1
