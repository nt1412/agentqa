# AgentQA Phase 2d — Requirements & Traceability

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add requirements management + requirement→test-case traceability, a coverage-gap report, and the final two MCP tools (`create_requirement`, `get_coverage_gaps`) — completing the agent surface (all 19 MCP tools real, zero stubs).

**Architecture:** Continues the established pattern exactly (transport-agnostic services, REST + MCP + CLI, savepoint-isolated TDD). All requirement tables already exist from the Phase 1 schema migration (`req_specs`, `requirements`, `req_versions`, `req_coverage`, `req_relations`) — **no new migration required**.

**Tech Stack:** Same as the rest of the project — FastAPI, SQLAlchemy 2.0 async, Pydantic v2, the `mcp` SDK, Typer, pytest, ruff.

**Context — why this phase:** Phase 2a/2b/2c gave plans, evidence, and self-correction. Phase 2d closes the loop back to *intent*: which requirements exist, which test cases cover them, and where coverage is missing. It implements the last two deferred MCP stubs so the curated agent toolset is complete.

**Coverage model:** a `req_coverage` row links a `req_version` to a `test_case_version`. "Covered" = a requirement version has ≥1 active coverage row. `get_coverage_gaps` returns requirement versions with zero active coverage. Coverage links target the test case's CURRENT active version (mirroring how `test_plan_cases` resolves versions in Phase 2a).

---

## File Structure

```
app/schemas/requirement.py   # ReqSpecCreate/Out, RequirementCreate/Out, ReqVersionOut,             (new)
                             # CoverageLink, CoverageGap, TraceabilityRow
app/services/requirements.py # create_req_spec, list_req_specs, create_requirement (+version+links), (new)
                             # link_coverage, list_requirements, get_coverage_gaps, get_traceability
app/api/requirements.py      # /projects/{id}/req-specs, /req-specs/{id}/requirements,               (new)
                             # /requirements/{id}/coverage, /projects/{id}/traceability,
                             # /projects/{id}/coverage-gaps
app/mcp_server/server.py     # implement create_requirement + get_coverage_gaps (remove last 2 stubs) (modify)
app/main.py                  # include requirements router                                            (modify)
cli/main.py                  # req verbs                                                              (modify)
tests/test_requirements.py, test_coverage.py, test_mcp_requirements.py                               (new)
```

**Design notes:**
- `create_requirement` is workflow-shaped: one call creates the `Requirement` + its `ReqVersion` (v1) + optional `ReqCoverage` rows to the current versions of the given case ids. This is the MCP tool's backing service.
- `get_coverage_gaps` is the inverse of traceability — it lists requirement versions lacking active coverage, optionally scoped to a spec.
- `_current_version_id` (resolving a case to its current active version) already exists in `app/services/plans.py`; import and reuse it rather than re-implementing.

---

## Task 1: Requirement Specs + Requirements (+ versions)

**Files:**
- Create: `app/schemas/requirement.py`, `app/services/requirements.py`, `app/api/requirements.py`
- Modify: `app/main.py`
- Test: `tests/test_requirements.py`

- [ ] **Step 1: Write `app/schemas/requirement.py`** (coverage/traceability schemas appended in Task 2)

```python
from pydantic import BaseModel


class ReqSpecCreate(BaseModel):
    doc_id: str
    name: str
    scope: str | None = None


class ReqSpecOut(BaseModel):
    id: int
    project_id: int
    doc_id: str
    name: str
    scope: str | None = None

    model_config = {"from_attributes": True}


class RequirementCreate(BaseModel):
    req_doc_id: str
    name: str
    scope: str | None = None
    link_to_cases: list[int] = []


class ReqVersionOut(BaseModel):
    id: int
    req_id: int
    version: int
    scope: str | None = None
    status: str | None = None

    model_config = {"from_attributes": True}


class RequirementOut(BaseModel):
    id: int
    spec_id: int
    req_doc_id: str
    name: str
    current_version: ReqVersionOut | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Write the failing test `tests/test_requirements.py`**

```python
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
        await requirements.create_req_spec(
            session, 9999, ReqSpecCreate(doc_id="X", name="x")
        )


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
```

- [ ] **Step 3: Run it — verify failure** (`.venv/bin/pytest tests/test_requirements.py -v`)

- [ ] **Step 4: Write `app/services/requirements.py`** (coverage/gaps/traceability appended in Task 2)

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.requirement import ReqSpec, Requirement, ReqVersion
from app.schemas.requirement import (
    ReqSpecCreate,
    RequirementCreate,
    RequirementOut,
    ReqVersionOut,
)
from app.services.errors import NotFound
from app.services.projects import get_project


async def create_req_spec(
    session: AsyncSession, project_id: int, data: ReqSpecCreate
) -> ReqSpec:
    await get_project(session, project_id)
    spec = ReqSpec(
        project_id=project_id, doc_id=data.doc_id, name=data.name, scope=data.scope
    )
    session.add(spec)
    await session.commit()
    await session.refresh(spec)
    return spec


async def list_req_specs(session: AsyncSession, project_id: int) -> list[ReqSpec]:
    stmt = select(ReqSpec).where(ReqSpec.project_id == project_id).order_by(ReqSpec.id)
    return list((await session.execute(stmt)).scalars().all())


async def create_requirement(
    session: AsyncSession, spec_id: int, data: RequirementCreate
):
    spec = await session.get(ReqSpec, spec_id)
    if spec is None:
        raise NotFound(f"req spec {spec_id} not found")
    req = Requirement(spec_id=spec_id, req_doc_id=data.req_doc_id, name=data.name)
    session.add(req)
    await session.flush()
    version = ReqVersion(req_id=req.id, version=1, scope=data.scope, status="draft")
    session.add(version)
    await session.flush()

    if data.link_to_cases:
        from app.services.requirements import link_coverage

        await link_coverage(session, version.id, data.link_to_cases)
    await session.commit()
    return await get_requirement(session, req.id)


async def _current_req_version(session: AsyncSession, req: Requirement) -> ReqVersion | None:
    stmt = (
        select(ReqVersion)
        .where(ReqVersion.req_id == req.id)
        .order_by(ReqVersion.version.desc())
    )
    return (await session.execute(stmt)).scalars().first()


async def get_requirement(session: AsyncSession, req_id: int) -> RequirementOut:
    req = await session.get(Requirement, req_id)
    if req is None:
        raise NotFound(f"requirement {req_id} not found")
    out = RequirementOut.model_validate(req)
    cur = await _current_req_version(session, req)
    out.current_version = ReqVersionOut.model_validate(cur) if cur else None
    return out


async def list_requirements(session: AsyncSession, spec_id: int) -> list[Requirement]:
    stmt = select(Requirement).where(Requirement.spec_id == spec_id).order_by(Requirement.id)
    return list((await session.execute(stmt)).scalars().all())
```

(Note: `selectinload` import is included for parity with other services; if ruff flags it unused, remove it.)

- [ ] **Step 5: Write `app/api/requirements.py`** (coverage/traceability routes appended in Task 2)

```python
from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.requirement import (
    ReqSpecCreate,
    ReqSpecOut,
    RequirementCreate,
    RequirementOut,
)
from app.services import requirements

router = APIRouter(prefix="/api/v1", tags=["requirements"])


@router.post(
    "/projects/{project_id}/req-specs",
    response_model=ReqSpecOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_spec(
    project_id: int, body: ReqSpecCreate, session: SessionDep, user: CurrentUser
):
    return await requirements.create_req_spec(session, project_id, body)


@router.get("/projects/{project_id}/req-specs", response_model=list[ReqSpecOut])
async def list_specs(project_id: int, session: SessionDep, user: CurrentUser):
    return await requirements.list_req_specs(session, project_id)


@router.post(
    "/req-specs/{spec_id}/requirements",
    response_model=RequirementOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_req(spec_id: int, body: RequirementCreate, session: SessionDep, user: CurrentUser):
    return await requirements.create_requirement(session, spec_id, body)


@router.get("/req-specs/{spec_id}/requirements", response_model=list[RequirementOut])
async def list_reqs(spec_id: int, session: SessionDep, user: CurrentUser):
    reqs = await requirements.list_requirements(session, spec_id)
    return [await requirements.get_requirement(session, r.id) for r in reqs]
```

- [ ] **Step 6: Wire router into `app/main.py`** — add `requirements` to the import and `app.include_router(requirements.router)`.

- [ ] **Step 7: Run tests + lint** — `tests/test_requirements.py` 4 pass; full suite green (111 → 115); ruff clean.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: requirement specs + requirements (versioned) service + endpoints"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## Task 2: Coverage Linking, Gaps & Traceability

**Files:**
- Modify: `app/schemas/requirement.py`, `app/services/requirements.py`, `app/api/requirements.py`
- Test: `tests/test_coverage.py`

- [ ] **Step 1: Append schemas to `app/schemas/requirement.py`**

```python
class CoverageLink(BaseModel):
    case_ids: list[int]


class CoverageGap(BaseModel):
    requirement_id: int
    req_version_id: int
    req_doc_id: str
    name: str


class TraceabilityRow(BaseModel):
    requirement_id: int
    req_doc_id: str
    name: str
    covered_case_ids: list[int] = []
```

- [ ] **Step 2: Write the failing test `tests/test_coverage.py`**

```python
import pytest

from app.schemas.project import ProjectCreate
from app.schemas.requirement import ReqSpecCreate, RequirementCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import projects, requirements, suites, testcases


async def _setup(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    spec = await requirements.create_req_spec(
        session, p.id, ReqSpecCreate(doc_id="SRS", name="Spec")
    )
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    return p, spec, tc


@pytest.mark.asyncio
async def test_create_requirement_with_coverage_links(session):
    p, spec, tc = await _setup(session, "CV1")
    req = await requirements.create_requirement(
        session, spec.id,
        RequirementCreate(req_doc_id="REQ-1", name="r", link_to_cases=[tc.id]),
    )
    trace = await requirements.get_traceability(session, p.id)
    assert len(trace) == 1
    assert trace[0].covered_case_ids == [tc.id]


@pytest.mark.asyncio
async def test_coverage_gaps(session):
    p, spec, tc = await _setup(session, "CV2")
    # one covered, one uncovered
    await requirements.create_requirement(
        session, spec.id,
        RequirementCreate(req_doc_id="REQ-1", name="covered", link_to_cases=[tc.id]),
    )
    await requirements.create_requirement(
        session, spec.id, RequirementCreate(req_doc_id="REQ-2", name="uncovered")
    )
    gaps = await requirements.get_coverage_gaps(session, p.id)
    assert len(gaps) == 1
    assert gaps[0].name == "uncovered"


@pytest.mark.asyncio
async def test_link_coverage_endpoint(client, auth_headers, session):
    p, spec, tc = await _setup(session, "CVE")
    req = await requirements.create_requirement(
        session, spec.id, RequirementCreate(req_doc_id="REQ-1", name="r")
    )
    # link via REST
    resp = await client.post(
        f"/api/v1/requirements/{req.id}/coverage",
        json={"case_ids": [tc.id]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    trace = await client.get(f"/api/v1/projects/{p.id}/traceability", headers=auth_headers)
    assert trace.json()[0]["covered_case_ids"] == [tc.id]


@pytest.mark.asyncio
async def test_coverage_gaps_endpoint(client, auth_headers, session):
    p, spec, tc = await _setup(session, "CGE")
    await requirements.create_requirement(
        session, spec.id, RequirementCreate(req_doc_id="REQ-1", name="uncovered")
    )
    resp = await client.get(f"/api/v1/projects/{p.id}/coverage-gaps", headers=auth_headers)
    assert resp.status_code == 200
    assert any(g["name"] == "uncovered" for g in resp.json())
```

- [ ] **Step 3: Run it — verify failure**

- [ ] **Step 4: Append to `app/services/requirements.py`**

Add imports: `from app.models.requirement import ReqCoverage`, `from app.models.testcase import TestCase, TestCaseVersion`, `from app.services.plans import _current_version_id`, and the new schemas `CoverageGap, TraceabilityRow`. Then:

```python
async def link_coverage(
    session: AsyncSession, req_version_id: int, case_ids: list[int]
) -> list[ReqCoverage]:
    created: list[ReqCoverage] = []
    for case_id in case_ids:
        case_version_id = await _current_version_id(session, case_id)
        existing = (
            await session.execute(
                select(ReqCoverage).where(
                    ReqCoverage.req_version_id == req_version_id,
                    ReqCoverage.case_version_id == case_version_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            created.append(existing)
            continue
        cov = ReqCoverage(
            req_version_id=req_version_id, case_version_id=case_version_id, is_active=True
        )
        session.add(cov)
        await session.flush()
        created.append(cov)
    return created


async def link_requirement_coverage(
    session: AsyncSession, req_id: int, case_ids: list[int]
) -> list[ReqCoverage]:
    req = await session.get(Requirement, req_id)
    if req is None:
        raise NotFound(f"requirement {req_id} not found")
    version = await _current_req_version(session, req)
    if version is None:
        raise NotFound(f"requirement {req_id} has no version")
    links = await link_coverage(session, version.id, case_ids)
    await session.commit()
    return links


async def get_coverage_gaps(
    session: AsyncSession, project_id: int, spec_id: int | None = None
) -> list[CoverageGap]:
    # current req version per requirement in the project, with no active coverage
    spec_stmt = select(ReqSpec.id).where(ReqSpec.project_id == project_id)
    if spec_id is not None:
        spec_stmt = spec_stmt.where(ReqSpec.id == spec_id)
    spec_ids = (await session.execute(spec_stmt)).scalars().all()
    if not spec_ids:
        return []
    reqs = (
        await session.execute(
            select(Requirement).where(Requirement.spec_id.in_(spec_ids))
        )
    ).scalars().all()

    gaps: list[CoverageGap] = []
    for req in reqs:
        version = await _current_req_version(session, req)
        if version is None:
            continue
        covered = (
            await session.execute(
                select(ReqCoverage.id).where(
                    ReqCoverage.req_version_id == version.id,
                    ReqCoverage.is_active.is_(True),
                )
            )
        ).first()
        if covered is None:
            gaps.append(
                CoverageGap(
                    requirement_id=req.id, req_version_id=version.id,
                    req_doc_id=req.req_doc_id, name=req.name,
                )
            )
    return gaps


async def get_traceability(
    session: AsyncSession, project_id: int, spec_id: int | None = None
) -> list[TraceabilityRow]:
    spec_stmt = select(ReqSpec.id).where(ReqSpec.project_id == project_id)
    if spec_id is not None:
        spec_stmt = spec_stmt.where(ReqSpec.id == spec_id)
    spec_ids = (await session.execute(spec_stmt)).scalars().all()
    if not spec_ids:
        return []
    reqs = (
        await session.execute(
            select(Requirement).where(Requirement.spec_id.in_(spec_ids)).order_by(Requirement.id)
        )
    ).scalars().all()

    rows: list[TraceabilityRow] = []
    for req in reqs:
        version = await _current_req_version(session, req)
        case_ids: list[int] = []
        if version is not None:
            # coverage -> case_version -> case
            cov_case_ids = (
                await session.execute(
                    select(TestCaseVersion.case_id)
                    .join(
                        ReqCoverage, ReqCoverage.case_version_id == TestCaseVersion.id
                    )
                    .where(
                        ReqCoverage.req_version_id == version.id,
                        ReqCoverage.is_active.is_(True),
                    )
                    .distinct()
                )
            ).scalars().all()
            case_ids = list(cov_case_ids)
        rows.append(
            TraceabilityRow(
                requirement_id=req.id, req_doc_id=req.req_doc_id,
                name=req.name, covered_case_ids=case_ids,
            )
        )
    return rows
```

- [ ] **Step 5: Append routes to `app/api/requirements.py`**

Add imports: `from app.schemas.requirement import CoverageGap, CoverageLink, TraceabilityRow`. Then:

```python
@router.post(
    "/requirements/{req_id}/coverage",
    response_model=list[dict],
    status_code=status.HTTP_201_CREATED,
)
async def link_coverage(req_id: int, body: CoverageLink, session: SessionDep, user: CurrentUser):
    links = await requirements.link_requirement_coverage(session, req_id, body.case_ids)
    return [{"id": link.id, "case_version_id": link.case_version_id} for link in links]


@router.get("/projects/{project_id}/traceability", response_model=list[TraceabilityRow])
async def traceability(project_id: int, session: SessionDep, user: CurrentUser):
    return await requirements.get_traceability(session, project_id)


@router.get("/projects/{project_id}/coverage-gaps", response_model=list[CoverageGap])
async def coverage_gaps(project_id: int, session: SessionDep, user: CurrentUser):
    return await requirements.get_coverage_gaps(session, project_id)
```

- [ ] **Step 6: Run tests + lint** — `tests/test_coverage.py` 4 pass; full suite green; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: coverage linking, gaps, and traceability"
```
Trailer as above.

---

## Task 3: MCP Tools + CLI + Final Verification

**Files:**
- Modify: `app/mcp_server/server.py`, `cli/main.py`
- Test: `tests/test_mcp_requirements.py`, `tests/test_cli.py` (append)

- [ ] **Step 1: Write the failing MCP test `tests/test_mcp_requirements.py`**

```python
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

    monkeypatch.setattr(mcp, "_session", lambda: _Ctx())


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
```

- [ ] **Step 2: Run it — verify failure**

- [ ] **Step 3: Implement the 2 tools in `app/mcp_server/server.py`**

REMOVE `"get_coverage_gaps"` and `"create_requirement"` from `_DEFERRED` — the list becomes EMPTY (`_DEFERRED = []`; the `for _name in _DEFERRED:` loop then registers nothing, which is fine). Add `from app.services import requirements` to imports and add the 2 real tools:

```python
@mcp.tool()
async def create_requirement(
    spec_id: int,
    req_doc_id: str,
    name: str,
    scope: str | None = None,
    link_to_cases: list[int] | None = None,
) -> dict:
    """Create a requirement (+v1) under a spec, optionally linking it to test cases."""
    from app.schemas.requirement import RequirementCreate

    async with _session() as s:
        out = await requirements.create_requirement(
            s,
            spec_id,
            RequirementCreate(
                req_doc_id=req_doc_id, name=name, scope=scope,
                link_to_cases=link_to_cases or [],
            ),
        )
        return {"id": out.id, "req_doc_id": out.req_doc_id, "name": out.name}


@mcp.tool()
async def get_coverage_gaps(project_id: int, spec_id: int | None = None) -> list[dict]:
    """Requirements with no active test coverage — gap analysis."""
    async with _session() as s:
        gaps = await requirements.get_coverage_gaps(s, project_id, spec_id)
        return [g.model_dump() for g in gaps]
```

- [ ] **Step 4: Append CLI verbs to `cli/main.py`**

```python
req_app = typer.Typer(help="Requirements & coverage")
app.add_typer(req_app, name="req")


@req_app.command("spec-create")
def req_spec_create(
    project_id: int, doc_id: str = typer.Option(..., "--doc-id"), name: str = typer.Option(..., "--name")
):
    _print(
        _request(
            "POST", f"/api/v1/projects/{project_id}/req-specs",
            json_body={"doc_id": doc_id, "name": name},
        )
    )


@req_app.command("create")
def req_create(spec_id: int, doc_id: str = typer.Option(..., "--doc-id"), name: str = typer.Option(..., "--name")):
    _print(
        _request(
            "POST", f"/api/v1/req-specs/{spec_id}/requirements",
            json_body={"req_doc_id": doc_id, "name": name},
        )
    )


@req_app.command("gaps")
def req_gaps(project_id: int):
    _print(_request("GET", f"/api/v1/projects/{project_id}/coverage-gaps"))


@req_app.command("traceability")
def req_traceability(project_id: int):
    _print(_request("GET", f"/api/v1/projects/{project_id}/traceability"))
```
Add a CLI test to `tests/test_cli.py`:
```python
def test_req_gaps_invokes_get(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_request", lambda m, p, **k: calls.append((m, p, k)) or [])
    result = runner.invoke(cli.app, ["req", "gaps", "3"])
    assert result.exit_code == 0
    assert calls[0][1] == "/api/v1/projects/3/coverage-gaps"
```

- [ ] **Step 5: Run tests + lint** — mcp_requirements + cli tests pass; full suite green; ruff clean across `app/ cli/ scripts/ tests/`.

- [ ] **Step 6: Verify the MCP surface is COMPLETE (19 tools, 0 stubs)**

```bash
.venv/bin/python -c "
import asyncio
from app.mcp_server import server as mcp
names = [t.name for t in asyncio.run(mcp.mcp.list_tools())]
print('tools:', len(names))
assert len(names) == 19, len(names)
for n in ['create_requirement','get_coverage_gaps']:
    assert n in names, n
# no NotImplementedError stubs remain: every tool should be callable
print('DEFERRED:', mcp._DEFERRED)
assert mcp._DEFERRED == [], mcp._DEFERRED
print('OK — all 19 MCP tools implemented')
"
```
Expected: `tools: 19`, `DEFERRED: []`, `OK`.

- [ ] **Step 7: MCP smoke** — `timeout 2 .venv/bin/python -m app.mcp_server.server || true` (no traceback).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: MCP create_requirement + get_coverage_gaps (all 19 tools implemented) + CLI"
```
Trailer as above.

---

## Phase 2d Done — What Exists

- Requirement specs + versioned requirements + coverage links (REST + MCP + CLI)
- Coverage-gap report + traceability matrix
- MCP surface COMPLETE: 19 tools, 0 stubs

## Deferred to Phase 3

- The Next.js supervision UI (Project Dashboard, Test Suite Browser, Test Case Editor, Execution Runner, Requirements Manager, Traceability Matrix, Reports, Agent Activity Feed, Evidence Viewer, Claim Audit Board, Admin).

---

## Self-Review

**Spec coverage:** req specs ✓, versioned requirements ✓, `create_requirement` with coverage links (workflow-shaped) ✓, coverage gaps ✓, traceability matrix ✓, 2 MCP tools ✓ (stubs 2→0), CLI ✓.
**Type consistency:** `create_requirement(session, spec_id, RequirementCreate)` returns a `RequirementOut` (via `get_requirement`), matching REST + MCP callers; `link_coverage(session, req_version_id, case_ids)` (internal, no commit) vs `link_requirement_coverage(session, req_id, case_ids)` (public, commits) — names distinct and used correctly (create_requirement calls the internal `link_coverage` within its own tx; the REST coverage endpoint calls `link_requirement_coverage`); `_current_version_id` reused from `app/services/plans.py`; `CoverageGap`/`TraceabilityRow` schemas match service returns and response_models; `_DEFERRED == []` after removing the last two names so the stub loop registers nothing.
**No placeholders:** every step has full code or exact commands.