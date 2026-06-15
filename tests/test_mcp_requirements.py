import pytest

from app.mcp_server import server as mcp
from app.schemas.project import ProjectCreate
from app.schemas.requirement import ReqSpecCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import projects, requirements, suites, testcases


@pytest.fixture(autouse=True)
def _use_test_session(session, monkeypatch):
    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(mcp, "_session", lambda *a, **k: _Ctx())


@pytest.mark.asyncio
async def test_create_requirement_and_gaps_via_mcp(session):
    p = await projects.create_project(session, ProjectCreate(name="M", prefix="MRQ"))
    spec = await requirements.create_req_spec(
        session, p.id, ReqSpecCreate(doc_id="SRS", name="Spec")
    )
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))

    req = await mcp.create_requirement(
        spec_id=spec.id, req_doc_id="REQ-1", name="covered", link_to_cases=[tc.id]
    )
    assert req["id"] is not None
    # an uncovered requirement shows up in gaps
    await mcp.create_requirement(spec_id=spec.id, req_doc_id="REQ-2", name="uncovered")
    gaps = await mcp.get_coverage_gaps(project_id=p.id)
    assert any(g["name"] == "uncovered" for g in gaps)
    assert all(g["name"] != "covered" for g in gaps)


@pytest.mark.asyncio
async def test_link_coverage_after_creation_via_mcp(session):
    # An agent registers a requirement up front, then links coverage as each test
    # lands later — the MCP surface must support post-hoc linking, not only at create.
    p = await projects.create_project(session, ProjectCreate(name="L", prefix="LNK"))
    spec = await requirements.create_req_spec(
        session, p.id, ReqSpecCreate(doc_id="SRS", name="Spec")
    )
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    req = await mcp.create_requirement(spec_id=spec.id, req_doc_id="REQ-1", name="later")

    # before linking → it's a gap
    gaps = await mcp.get_coverage_gaps(project_id=p.id)
    assert any(g["name"] == "later" for g in gaps)

    # link coverage after creation
    out = await mcp.link_coverage(req_id=req["id"], case_ids=[tc.id])
    assert out["req_id"] == req["id"]
    assert out["linked_case_ids"] == [tc.id]

    # after linking → no longer a gap
    gaps = await mcp.get_coverage_gaps(project_id=p.id)
    assert all(g["name"] != "later" for g in gaps)
