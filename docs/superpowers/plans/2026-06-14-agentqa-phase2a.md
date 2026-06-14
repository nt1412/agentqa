# AgentQA Phase 2a — Plans, Builds, Milestones, Assignments

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the "planning" entities — platforms, test plans (+ case/platform links), builds, milestones, and assignments — through the public service layer, REST API, CLI, and (for assignments) MCP, so an agent or human can manage the full execution-tracking surface without ORM workarounds.

**Architecture:** Continues the Phase 1 pattern exactly: transport-agnostic async services in `app/services/` (raise domain errors from `app/services/errors.py`, never import FastAPI), thin FastAPI routers in `app/api/`, Pydantic schemas in `app/schemas/`, MCP tools wrapping services in `app/mcp_server/server.py`, Typer verbs in `cli/main.py`. All models already exist (created in the Phase 1 schema migration); this phase only adds services/endpoints/tools on top — **no new migration is required**.

**Tech Stack:** Same as Phase 1 — FastAPI, SQLAlchemy 2.0 async, Pydantic v2, the `mcp` SDK, Typer, pytest (savepoint-isolated `session`/`client`/`auth_headers` fixtures), ruff.

**Context — why this phase:** Phase 1 shipped execution recording but no way to create a test plan or build via the API; the dogfood script (`scripts/dogfood.py`) had to create the `TestPlan` via the ORM. This phase closes that gap. It is the prerequisite for Phase 2b (evidence/claims/self-correction), which records claims and reasoning against executions that live under plans/builds.

**Motivating fact to preserve:** `executions.record_execution` already upserts a `Build` by `(plan_id, build_name)` and there is a unique constraint `uq_builds_plan_name`. The explicit Build API added here must reuse/agree with that upsert (same find-or-create semantics), not fight it.

---

## File Structure

```
app/schemas/
  platform.py     # PlatformCreate, PlatformOut                         (new)
  plan.py         # PlanCreate, PlanUpdate, PlanOut, PlanCaseAdd,        (new)
                  # PlanCaseOut, BuildCreate, BuildOut, MilestoneCreate, MilestoneOut
  assignment.py   # AssignmentCreate, AssignmentUpdate, AssignmentOut    (new)
app/services/
  platforms.py    # create_platform, list_platforms, get_platform       (new)
  plans.py        # plan CRUD, add/remove cases, list cases, link platforms (new)
  builds.py       # create_build (find-or-create), list_builds, get_build (new)
  milestones.py   # create_milestone, list_milestones                   (new)
  assignments.py  # create_assignment, list_assignments, update_assignment (new)
app/api/
  platforms.py    # /projects/{id}/platforms                            (new)
  plans.py        # /projects/{id}/plans, /plans/{id}, cases, builds, milestones (new)
  assignments.py  # /assignments                                        (new)
app/mcp_server/server.py   # implement list_assignments + assign_test (remove 2 stubs) (modify)
cli/main.py        # plan/build/milestone/assign verb groups            (modify)
app/main.py        # include platforms, plans, assignments routers       (modify)
tests/
  test_platforms.py, test_plans.py, test_builds.py,
  test_milestones.py, test_assignments.py, test_mcp_assignments.py      (new)
```

**Design notes:**
- `builds.create_build` MUST use find-or-create on `(plan_id, name)` (mirroring `executions._upsert_build`) so the explicit API and the implicit execution-time upsert never collide on the unique constraint.
- `plans.py` owns both the plan entity and its junction tables (`test_plan_cases`, `test_plan_platforms`) — they change together, so they live together.
- Assignments get an MCP surface (`list_assignments`, `assign_test`) because agents poll/assign; plans/builds/milestones stay REST+CLI only (admin-shaped), per the design's MCP-is-the-curated-subset rule.

---

## Task 1: Platforms — Service + Endpoints

Platforms are referenced by plan-case links and executions. Minimal CRUD (create/list/get).

**Files:**
- Create: `app/schemas/platform.py`, `app/services/platforms.py`, `app/api/platforms.py`
- Modify: `app/main.py`
- Test: `tests/test_platforms.py`

- [ ] **Step 1: Write `app/schemas/platform.py`**

```python
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
```

- [ ] **Step 2: Write the failing test `tests/test_platforms.py`**

```python
import pytest

from app.schemas.platform import PlatformCreate
from app.schemas.project import ProjectCreate
from app.services import platforms, projects
from app.services.errors import NotFound


@pytest.mark.asyncio
async def test_create_and_list_platform(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PL1"))
    plat = await platforms.create_platform(session, p.id, PlatformCreate(name="Linux"))
    assert plat.id is not None
    rows = await platforms.list_platforms(session, p.id)
    assert [r.name for r in rows] == ["Linux"]


@pytest.mark.asyncio
async def test_create_platform_unknown_project(session):
    with pytest.raises(NotFound):
        await platforms.create_platform(session, 9999, PlatformCreate(name="X"))


@pytest.mark.asyncio
async def test_platform_endpoints(client, auth_headers):
    pc = await client.post(
        "/api/v1/projects", json={"name": "P", "prefix": "PLE"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    create = await client.post(
        f"/api/v1/projects/{pid}/platforms", json={"name": "Win"}, headers=auth_headers
    )
    assert create.status_code == 201
    listed = await client.get(f"/api/v1/projects/{pid}/platforms", headers=auth_headers)
    assert any(p["name"] == "Win" for p in listed.json())
```

- [ ] **Step 3: Run it — verify failure**

Run: `.venv/bin/pytest tests/test_platforms.py -v`
Expected: FAIL (module/route missing).

- [ ] **Step 4: Write `app/services/platforms.py`**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.structure import Platform
from app.schemas.platform import PlatformCreate
from app.services.errors import NotFound
from app.services.projects import get_project


async def create_platform(
    session: AsyncSession, project_id: int, data: PlatformCreate
) -> Platform:
    await get_project(session, project_id)  # raises NotFound if absent
    platform = Platform(project_id=project_id, name=data.name, notes=data.notes)
    session.add(platform)
    await session.commit()
    await session.refresh(platform)
    return platform


async def get_platform(session: AsyncSession, platform_id: int) -> Platform:
    platform = await session.get(Platform, platform_id)
    if platform is None:
        raise NotFound(f"platform {platform_id} not found")
    return platform


async def list_platforms(session: AsyncSession, project_id: int) -> list[Platform]:
    stmt = select(Platform).where(Platform.project_id == project_id).order_by(Platform.id)
    return list((await session.execute(stmt)).scalars().all())
```

- [ ] **Step 5: Write `app/api/platforms.py`**

```python
from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.platform import PlatformCreate, PlatformOut
from app.services import platforms

router = APIRouter(prefix="/api/v1", tags=["platforms"])


@router.post(
    "/projects/{project_id}/platforms",
    response_model=PlatformOut,
    status_code=status.HTTP_201_CREATED,
)
async def create(project_id: int, body: PlatformCreate, session: SessionDep, user: CurrentUser):
    return await platforms.create_platform(session, project_id, body)


@router.get("/projects/{project_id}/platforms", response_model=list[PlatformOut])
async def list_all(project_id: int, session: SessionDep, user: CurrentUser):
    return await platforms.list_platforms(session, project_id)
```

- [ ] **Step 6: Wire router into `app/main.py`**

Update the import + includes inside `create_app()` to add `platforms`:
```python
    from app.api import auth, executions, platforms, projects, suites, testcases

    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(suites.router)
    app.include_router(testcases.router)
    app.include_router(executions.router)
    app.include_router(platforms.router)
```

- [ ] **Step 7: Run tests + lint**

Run: `.venv/bin/pytest tests/test_platforms.py -v` → 3 PASS; then `.venv/bin/pytest -q` → all pass.
`.venv/bin/ruff check --fix app/ tests/ && .venv/bin/ruff format app/ tests/`; confirm `.venv/bin/ruff check app/ cli/ scripts/ tests/` clean.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: platforms service + endpoints"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## Task 2: Test Plans — Service + Endpoints

Plan CRUD (create/get/list/update). Junction tables handled in Task 3.

**Files:**
- Create: `app/schemas/plan.py` (start it here; extended in Tasks 3-5), `app/services/plans.py`, `app/api/plans.py`
- Modify: `app/main.py`
- Test: `tests/test_plans.py`

- [ ] **Step 1: Write `app/schemas/plan.py`** (initial — Build/Milestone/Case schemas appended in later tasks)

```python
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
```

- [ ] **Step 2: Write the failing test `tests/test_plans.py`**

```python
import pytest

from app.schemas.plan import PlanCreate, PlanUpdate
from app.schemas.project import ProjectCreate
from app.services import plans, projects
from app.services.errors import NotFound


@pytest.mark.asyncio
async def test_create_and_get_plan(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PN1"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Release 1"))
    assert plan.id is not None
    fetched = await plans.get_plan(session, plan.id)
    assert fetched.name == "Release 1"
    assert fetched.is_open is True


@pytest.mark.asyncio
async def test_create_plan_unknown_project(session):
    with pytest.raises(NotFound):
        await plans.create_plan(session, 9999, PlanCreate(name="X"))


@pytest.mark.asyncio
async def test_update_plan(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PN2"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="A"))
    updated = await plans.update_plan(session, plan.id, PlanUpdate(is_open=False))
    assert updated.is_open is False
    assert updated.name == "A"


@pytest.mark.asyncio
async def test_list_plans(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PN3"))
    await plans.create_plan(session, p.id, PlanCreate(name="A"))
    await plans.create_plan(session, p.id, PlanCreate(name="B"))
    rows = await plans.list_plans(session, p.id)
    assert {r.name for r in rows} == {"A", "B"}


@pytest.mark.asyncio
async def test_plan_endpoints(client, auth_headers):
    pc = await client.post(
        "/api/v1/projects", json={"name": "P", "prefix": "PNE"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    create = await client.post(
        f"/api/v1/projects/{pid}/plans", json={"name": "Sprint 1"}, headers=auth_headers
    )
    assert create.status_code == 201
    plan_id = create.json()["id"]
    got = await client.get(f"/api/v1/plans/{plan_id}", headers=auth_headers)
    assert got.json()["name"] == "Sprint 1"
```

- [ ] **Step 3: Run it — verify failure** (`.venv/bin/pytest tests/test_plans.py -v`)

- [ ] **Step 4: Write `app/services/plans.py`** (case/platform functions appended in Task 3)

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import TestPlan
from app.schemas.plan import PlanCreate, PlanUpdate
from app.services.errors import NotFound
from app.services.projects import get_project


async def create_plan(session: AsyncSession, project_id: int, data: PlanCreate) -> TestPlan:
    await get_project(session, project_id)
    plan = TestPlan(project_id=project_id, name=data.name, notes=data.notes)
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return plan


async def get_plan(session: AsyncSession, plan_id: int) -> TestPlan:
    plan = await session.get(TestPlan, plan_id)
    if plan is None:
        raise NotFound(f"test plan {plan_id} not found")
    return plan


async def list_plans(session: AsyncSession, project_id: int) -> list[TestPlan]:
    stmt = select(TestPlan).where(TestPlan.project_id == project_id).order_by(TestPlan.id)
    return list((await session.execute(stmt)).scalars().all())


async def update_plan(session: AsyncSession, plan_id: int, data: PlanUpdate) -> TestPlan:
    plan = await get_plan(session, plan_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await session.commit()
    await session.refresh(plan)
    return plan
```

- [ ] **Step 5: Write `app/api/plans.py`** (case/build/milestone routes appended in later tasks)

```python
from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.plan import PlanCreate, PlanOut, PlanUpdate
from app.services import plans

router = APIRouter(prefix="/api/v1", tags=["plans"])


@router.post(
    "/projects/{project_id}/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED
)
async def create(project_id: int, body: PlanCreate, session: SessionDep, user: CurrentUser):
    return await plans.create_plan(session, project_id, body)


@router.get("/projects/{project_id}/plans", response_model=list[PlanOut])
async def list_all(project_id: int, session: SessionDep, user: CurrentUser):
    return await plans.list_plans(session, project_id)


@router.get("/plans/{plan_id}", response_model=PlanOut)
async def get_one(plan_id: int, session: SessionDep, user: CurrentUser):
    return await plans.get_plan(session, plan_id)


@router.put("/plans/{plan_id}", response_model=PlanOut)
async def update(plan_id: int, body: PlanUpdate, session: SessionDep, user: CurrentUser):
    return await plans.update_plan(session, plan_id, body)
```

- [ ] **Step 6: Wire router into `app/main.py`** — add `plans` to the import and `app.include_router(plans.router)`.

- [ ] **Step 7: Run tests + lint** — `tests/test_plans.py` 5 PASS; full suite green; ruff clean.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: test plans service + endpoints"
```
Trailer as above.

---

## Task 3: Plan ↔ Cases & Platforms — Linking

Add cases (by current version) and platforms to a plan; list/remove. Uses `test_plan_cases` and `test_plan_platforms`.

**Files:**
- Modify: `app/schemas/plan.py`, `app/services/plans.py`, `app/api/plans.py`
- Test: `tests/test_plans.py` (append)

- [ ] **Step 1: Append schemas to `app/schemas/plan.py`**

```python
class PlanCaseAdd(BaseModel):
    case_ids: list[int]
    platform_id: int | None = None
    urgency: int = 2


class PlanCaseOut(BaseModel):
    id: int
    plan_id: int
    version_id: int
    platform_id: int | None
    urgency: int

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Append failing tests to `tests/test_plans.py`**

```python
@pytest.mark.asyncio
async def test_add_and_list_plan_cases(session):
    from app.schemas.suite import SuiteCreate
    from app.schemas.testcase import TestCaseCreate
    from app.services import suites, testcases

    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PC1"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))

    links = await plans.add_cases(session, plan.id, [tc.id])
    assert len(links) == 1
    listed = await plans.list_plan_cases(session, plan.id)
    assert len(listed) == 1
    # the link points at the case's current active version
    assert listed[0].version_id is not None


@pytest.mark.asyncio
async def test_add_case_twice_is_idempotent(session):
    from app.schemas.suite import SuiteCreate
    from app.schemas.testcase import TestCaseCreate
    from app.services import suites, testcases

    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PC2"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    await plans.add_cases(session, plan.id, [tc.id])
    await plans.add_cases(session, plan.id, [tc.id])  # second add must not duplicate
    listed = await plans.list_plan_cases(session, plan.id)
    assert len(listed) == 1


@pytest.mark.asyncio
async def test_remove_plan_case(session):
    from app.schemas.suite import SuiteCreate
    from app.schemas.testcase import TestCaseCreate
    from app.services import suites, testcases

    p = await projects.create_project(session, ProjectCreate(name="P", prefix="PC3"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    await plans.add_cases(session, plan.id, [tc.id])
    await plans.remove_case(session, plan.id, tc.id)
    assert await plans.list_plan_cases(session, plan.id) == []


@pytest.mark.asyncio
async def test_add_cases_endpoint(client, auth_headers, session):
    pc = await client.post(
        "/api/v1/projects", json={"name": "P", "prefix": "PCE"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    sc = await client.post(
        f"/api/v1/projects/{pid}/suites", json={"name": "S"}, headers=auth_headers
    )
    cc = await client.post(
        f"/api/v1/suites/{sc.json()['id']}/cases", json={"name": "c"}, headers=auth_headers
    )
    plan = await client.post(
        f"/api/v1/projects/{pid}/plans", json={"name": "Plan"}, headers=auth_headers
    )
    plan_id = plan.json()["id"]
    add = await client.post(
        f"/api/v1/plans/{plan_id}/cases",
        json={"case_ids": [cc.json()["id"]]},
        headers=auth_headers,
    )
    assert add.status_code == 201
    listed = await client.get(f"/api/v1/plans/{plan_id}/cases", headers=auth_headers)
    assert len(listed.json()) == 1
```

- [ ] **Step 3: Run it — verify failure**

- [ ] **Step 4: Append to `app/services/plans.py`**

Add these imports at the top (merge with existing): `from app.models.plan import TestPlanCase` and `from app.models.testcase import TestCaseVersion`. Then add:

```python
async def _current_version_id(session: AsyncSession, case_id: int) -> int:
    stmt = (
        select(TestCaseVersion)
        .where(TestCaseVersion.case_id == case_id, TestCaseVersion.active.is_(True))
        .order_by(TestCaseVersion.version.desc())
    )
    v = (await session.execute(stmt)).scalars().first()
    if v is None:
        raise NotFound(f"test case {case_id} has no active version")
    return v.id


async def add_cases(
    session: AsyncSession,
    plan_id: int,
    case_ids: list[int],
    platform_id: int | None = None,
    urgency: int = 2,
) -> list[TestPlanCase]:
    await get_plan(session, plan_id)
    created: list[TestPlanCase] = []
    for case_id in case_ids:
        version_id = await _current_version_id(session, case_id)
        existing = (
            await session.execute(
                select(TestPlanCase).where(
                    TestPlanCase.plan_id == plan_id,
                    TestPlanCase.version_id == version_id,
                    TestPlanCase.platform_id.is_(platform_id)
                    if platform_id is None
                    else TestPlanCase.platform_id == platform_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            created.append(existing)
            continue
        link = TestPlanCase(
            plan_id=plan_id, version_id=version_id, platform_id=platform_id, urgency=urgency
        )
        session.add(link)
        await session.flush()
        created.append(link)
    await session.commit()
    return created


async def list_plan_cases(session: AsyncSession, plan_id: int) -> list[TestPlanCase]:
    stmt = (
        select(TestPlanCase)
        .where(TestPlanCase.plan_id == plan_id)
        .order_by(TestPlanCase.id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def remove_case(session: AsyncSession, plan_id: int, case_id: int) -> None:
    version_id = await _current_version_id(session, case_id)
    stmt = select(TestPlanCase).where(
        TestPlanCase.plan_id == plan_id, TestPlanCase.version_id == version_id
    )
    for link in (await session.execute(stmt)).scalars().all():
        await session.delete(link)
    await session.commit()
```

- [ ] **Step 5: Append routes to `app/api/plans.py`**

Add imports: `from app.schemas.plan import PlanCaseAdd, PlanCaseOut`. Then:

```python
@router.post(
    "/plans/{plan_id}/cases",
    response_model=list[PlanCaseOut],
    status_code=status.HTTP_201_CREATED,
)
async def add_cases(plan_id: int, body: PlanCaseAdd, session: SessionDep, user: CurrentUser):
    return await plans.add_cases(
        session, plan_id, body.case_ids, body.platform_id, body.urgency
    )


@router.get("/plans/{plan_id}/cases", response_model=list[PlanCaseOut])
async def list_cases(plan_id: int, session: SessionDep, user: CurrentUser):
    return await plans.list_plan_cases(session, plan_id)
```

- [ ] **Step 6: Run tests + lint** — new plan tests PASS; full suite green; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: link test cases to plans (add/list/remove, idempotent)"
```
Trailer as above.

---

## Task 4: Builds — Service + Endpoints (find-or-create)

Expose build creation/listing. `create_build` MUST use the SAME find-or-create on `(plan_id, name)` that `executions._upsert_build` uses, so the explicit API and the execution-time upsert agree and never violate `uq_builds_plan_name`.

**Files:**
- Modify: `app/schemas/plan.py`, `app/api/plans.py`
- Create: `app/services/builds.py`
- Test: `tests/test_builds.py`

- [ ] **Step 1: Append Build schemas to `app/schemas/plan.py`**

```python
import datetime as dt


class BuildCreate(BaseModel):
    name: str
    notes: str | None = None
    tag: str | None = None
    branch: str | None = None
    commit_id: str | None = None


class BuildOut(BaseModel):
    id: int
    plan_id: int
    name: str
    notes: str | None = None
    tag: str | None = None
    branch: str | None = None
    commit_id: str | None = None
    active: bool

    model_config = {"from_attributes": True}
```
(If `import datetime as dt` is unused after this, omit it — these fields are all str/optional; do NOT add unused imports. The `release_date` column exists on the model but is not exposed in Phase 2a.)

- [ ] **Step 2: Write the failing test `tests/test_builds.py`**

```python
import pytest

from app.schemas.plan import BuildCreate, PlanCreate
from app.schemas.project import ProjectCreate
from app.services import builds, plans, projects
from app.services.errors import NotFound


async def _plan(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    return plan


@pytest.mark.asyncio
async def test_create_build(session):
    plan = await _plan(session, "B1")
    b = await builds.create_build(session, plan.id, BuildCreate(name="v1", commit_id="abc"))
    assert b.id is not None
    assert b.commit_id == "abc"


@pytest.mark.asyncio
async def test_create_build_is_find_or_create(session):
    plan = await _plan(session, "B2")
    b1 = await builds.create_build(session, plan.id, BuildCreate(name="v1"))
    b2 = await builds.create_build(session, plan.id, BuildCreate(name="v1", commit_id="def"))
    assert b2.id == b1.id  # same (plan, name) -> same build
    assert b2.commit_id == "def"  # commit_id backfilled


@pytest.mark.asyncio
async def test_create_build_unknown_plan(session):
    with pytest.raises(NotFound):
        await builds.create_build(session, 9999, BuildCreate(name="v1"))


@pytest.mark.asyncio
async def test_list_builds(session):
    plan = await _plan(session, "B3")
    await builds.create_build(session, plan.id, BuildCreate(name="v1"))
    await builds.create_build(session, plan.id, BuildCreate(name="v2"))
    rows = await builds.list_builds(session, plan.id)
    assert {b.name for b in rows} == {"v1", "v2"}


@pytest.mark.asyncio
async def test_build_endpoints(client, auth_headers):
    pc = await client.post(
        "/api/v1/projects", json={"name": "P", "prefix": "BE"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    plan = await client.post(
        f"/api/v1/projects/{pid}/plans", json={"name": "Plan"}, headers=auth_headers
    )
    plan_id = plan.json()["id"]
    create = await client.post(
        f"/api/v1/plans/{plan_id}/builds", json={"name": "v1", "tag": "1.0"}, headers=auth_headers
    )
    assert create.status_code == 201
    listed = await client.get(f"/api/v1/plans/{plan_id}/builds", headers=auth_headers)
    assert any(b["name"] == "v1" for b in listed.json())
```

- [ ] **Step 3: Run it — verify failure**

- [ ] **Step 4: Write `app/services/builds.py`**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Build
from app.schemas.plan import BuildCreate
from app.services.errors import NotFound
from app.services.plans import get_plan


async def create_build(session: AsyncSession, plan_id: int, data: BuildCreate) -> Build:
    """Find-or-create by (plan_id, name); backfill metadata on existing builds.

    Mirrors executions._upsert_build so the explicit API and execution-time
    upsert agree on the unique (plan_id, name) constraint.
    """
    await get_plan(session, plan_id)  # raises NotFound if absent
    existing = (
        await session.execute(
            select(Build).where(Build.plan_id == plan_id, Build.name == data.name)
        )
    ).scalar_one_or_none()
    if existing is not None:
        if data.commit_id and not existing.commit_id:
            existing.commit_id = data.commit_id
        if data.tag and not existing.tag:
            existing.tag = data.tag
        if data.branch and not existing.branch:
            existing.branch = data.branch
        await session.commit()
        await session.refresh(existing)
        return existing
    build = Build(
        plan_id=plan_id,
        name=data.name,
        notes=data.notes,
        tag=data.tag,
        branch=data.branch,
        commit_id=data.commit_id,
    )
    session.add(build)
    await session.commit()
    await session.refresh(build)
    return build


async def get_build(session: AsyncSession, build_id: int) -> Build:
    build = await session.get(Build, build_id)
    if build is None:
        raise NotFound(f"build {build_id} not found")
    return build


async def list_builds(session: AsyncSession, plan_id: int) -> list[Build]:
    stmt = select(Build).where(Build.plan_id == plan_id).order_by(Build.id)
    return list((await session.execute(stmt)).scalars().all())
```

- [ ] **Step 5: Append routes to `app/api/plans.py`**

Add imports: `from app.schemas.plan import BuildCreate, BuildOut` and `from app.services import builds`. Then:

```python
@router.post(
    "/plans/{plan_id}/builds", response_model=BuildOut, status_code=status.HTTP_201_CREATED
)
async def create_build(plan_id: int, body: BuildCreate, session: SessionDep, user: CurrentUser):
    return await builds.create_build(session, plan_id, body)


@router.get("/plans/{plan_id}/builds", response_model=list[BuildOut])
async def list_builds(plan_id: int, session: SessionDep, user: CurrentUser):
    return await builds.list_builds(session, plan_id)
```

- [ ] **Step 6: Run tests + lint** — `tests/test_builds.py` 5 PASS; full suite green; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: builds service (find-or-create) + endpoints"
```
Trailer as above.

---

## Task 5: Milestones — Service + Endpoints

**Files:**
- Modify: `app/schemas/plan.py`, `app/api/plans.py`
- Create: `app/services/milestones.py`
- Test: `tests/test_milestones.py`

- [ ] **Step 1: Append Milestone schemas to `app/schemas/plan.py`**

Ensure `import datetime as dt` is present at the top of the file (add it if not already there).

```python
class MilestoneCreate(BaseModel):
    name: str
    target_date: dt.datetime | None = None
    start_date: dt.datetime | None = None


class MilestoneOut(BaseModel):
    id: int
    plan_id: int
    name: str
    target_date: dt.datetime | None = None
    start_date: dt.datetime | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Write the failing test `tests/test_milestones.py`**

```python
import datetime as dt

import pytest

from app.schemas.plan import MilestoneCreate, PlanCreate
from app.schemas.project import ProjectCreate
from app.services import milestones, plans, projects
from app.services.errors import NotFound


async def _plan(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    return await plans.create_plan(session, p.id, PlanCreate(name="Plan"))


@pytest.mark.asyncio
async def test_create_and_list_milestone(session):
    plan = await _plan(session, "MS1")
    target = dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc)
    m = await milestones.create_milestone(
        session, plan.id, MilestoneCreate(name="Beta", target_date=target)
    )
    assert m.id is not None
    rows = await milestones.list_milestones(session, plan.id)
    assert [r.name for r in rows] == ["Beta"]


@pytest.mark.asyncio
async def test_create_milestone_unknown_plan(session):
    with pytest.raises(NotFound):
        await milestones.create_milestone(session, 9999, MilestoneCreate(name="X"))


@pytest.mark.asyncio
async def test_milestone_endpoints(client, auth_headers):
    pc = await client.post(
        "/api/v1/projects", json={"name": "P", "prefix": "MSE"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    plan = await client.post(
        f"/api/v1/projects/{pid}/plans", json={"name": "Plan"}, headers=auth_headers
    )
    plan_id = plan.json()["id"]
    create = await client.post(
        f"/api/v1/plans/{plan_id}/milestones", json={"name": "GA"}, headers=auth_headers
    )
    assert create.status_code == 201
    listed = await client.get(f"/api/v1/plans/{plan_id}/milestones", headers=auth_headers)
    assert any(m["name"] == "GA" for m in listed.json())
```

- [ ] **Step 3: Run it — verify failure**

- [ ] **Step 4: Write `app/services/milestones.py`**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Milestone
from app.schemas.plan import MilestoneCreate
from app.services.plans import get_plan


async def create_milestone(
    session: AsyncSession, plan_id: int, data: MilestoneCreate
) -> Milestone:
    await get_plan(session, plan_id)  # raises NotFound if absent
    milestone = Milestone(
        plan_id=plan_id, name=data.name,
        target_date=data.target_date, start_date=data.start_date,
    )
    session.add(milestone)
    await session.commit()
    await session.refresh(milestone)
    return milestone


async def list_milestones(session: AsyncSession, plan_id: int) -> list[Milestone]:
    stmt = select(Milestone).where(Milestone.plan_id == plan_id).order_by(Milestone.id)
    return list((await session.execute(stmt)).scalars().all())
```

- [ ] **Step 5: Append routes to `app/api/plans.py`**

Add imports: `from app.schemas.plan import MilestoneCreate, MilestoneOut` and `from app.services import milestones`. Then:

```python
@router.post(
    "/plans/{plan_id}/milestones",
    response_model=MilestoneOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_milestone(
    plan_id: int, body: MilestoneCreate, session: SessionDep, user: CurrentUser
):
    return await milestones.create_milestone(session, plan_id, body)


@router.get("/plans/{plan_id}/milestones", response_model=list[MilestoneOut])
async def list_milestones(plan_id: int, session: SessionDep, user: CurrentUser):
    return await milestones.list_milestones(session, plan_id)
```

- [ ] **Step 6: Run tests + lint** — `tests/test_milestones.py` 3 PASS; full suite green; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: milestones service + endpoints"
```
Trailer as above.

---

## Task 6: Assignments — Service + Endpoints + MCP tools

Assignments target a human or an agent. This task adds the service, REST endpoints, AND implements two of the deferred MCP stubs: `list_assignments` and `assign_test`.

**Files:**
- Create: `app/schemas/assignment.py`, `app/services/assignments.py`, `app/api/assignments.py`
- Modify: `app/main.py`, `app/mcp_server/server.py`
- Test: `tests/test_assignments.py`, `tests/test_mcp_assignments.py`

- [ ] **Step 1: Write `app/schemas/assignment.py`**

```python
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
```

- [ ] **Step 2: Write the failing test `tests/test_assignments.py`**

```python
import pytest

from app.schemas.assignment import AssignmentCreate, AssignmentUpdate
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import assignments, plans, projects, suites, testcases


async def _case_and_plan(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    return tc, plan


@pytest.mark.asyncio
async def test_create_and_list_assignment(session, user):
    tc, plan = await _case_and_plan(session, "AS1")
    a = await assignments.create_assignment(
        session,
        AssignmentCreate(
            case_id=tc.id, plan_id=plan.id, assignee_id=user.id, assignee_type="human"
        ),
        assigner_id=user.id,
    )
    assert a.id is not None
    assert a.status == "open"
    rows = await assignments.list_assignments(session, plan_id=plan.id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_list_filters_by_assignee(session, user):
    tc, plan = await _case_and_plan(session, "AS2")
    await assignments.create_assignment(
        session,
        AssignmentCreate(
            case_id=tc.id, plan_id=plan.id, assignee_id=user.id, assignee_type="agent"
        ),
        assigner_id=None,
    )
    mine = await assignments.list_assignments(session, assignee_id=user.id)
    assert len(mine) == 1
    none = await assignments.list_assignments(session, assignee_id=999999)
    assert none == []


@pytest.mark.asyncio
async def test_update_assignment_status(session, user):
    tc, plan = await _case_and_plan(session, "AS3")
    a = await assignments.create_assignment(
        session,
        AssignmentCreate(
            case_id=tc.id, plan_id=plan.id, assignee_id=user.id, assignee_type="human"
        ),
        assigner_id=user.id,
    )
    updated = await assignments.update_assignment(
        session, a.id, AssignmentUpdate(status="in_progress")
    )
    assert updated.status == "in_progress"


@pytest.mark.asyncio
async def test_assignment_endpoints(client, auth_headers, user, session):
    tc, plan = await _case_and_plan(session, "ASE")
    create = await client.post(
        "/api/v1/assignments",
        json={
            "case_id": tc.id, "plan_id": plan.id,
            "assignee_id": user.id, "assignee_type": "human",
        },
        headers=auth_headers,
    )
    assert create.status_code == 201
    listed = await client.get(
        f"/api/v1/assignments?plan_id={plan.id}", headers=auth_headers
    )
    assert len(listed.json()) == 1
```

- [ ] **Step 3: Run it — verify failure**

- [ ] **Step 4: Write `app/services/assignments.py`**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Assignment
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate
from app.services.errors import NotFound


async def create_assignment(
    session: AsyncSession, data: AssignmentCreate, assigner_id: int | None
) -> Assignment:
    assignment = Assignment(
        case_id=data.case_id,
        plan_id=data.plan_id,
        build_id=data.build_id,
        assignee_id=data.assignee_id,
        assignee_type=data.assignee_type,
        deadline=data.deadline,
        status="open",
        assigner_id=assigner_id,
    )
    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment


async def get_assignment(session: AsyncSession, assignment_id: int) -> Assignment:
    assignment = await session.get(Assignment, assignment_id)
    if assignment is None:
        raise NotFound(f"assignment {assignment_id} not found")
    return assignment


async def list_assignments(
    session: AsyncSession,
    plan_id: int | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
) -> list[Assignment]:
    stmt = select(Assignment)
    if plan_id is not None:
        stmt = stmt.where(Assignment.plan_id == plan_id)
    if assignee_id is not None:
        stmt = stmt.where(Assignment.assignee_id == assignee_id)
    if status is not None:
        stmt = stmt.where(Assignment.status == status)
    stmt = stmt.order_by(Assignment.id)
    return list((await session.execute(stmt)).scalars().all())


async def update_assignment(
    session: AsyncSession, assignment_id: int, data: AssignmentUpdate
) -> Assignment:
    assignment = await get_assignment(session, assignment_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(assignment, field, value)
    await session.commit()
    await session.refresh(assignment)
    return assignment
```

- [ ] **Step 5: Write `app/api/assignments.py`**

```python
from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.assignment import AssignmentCreate, AssignmentOut, AssignmentUpdate
from app.services import assignments

router = APIRouter(prefix="/api/v1/assignments", tags=["assignments"])


@router.post("", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def create(body: AssignmentCreate, session: SessionDep, user: CurrentUser):
    return await assignments.create_assignment(session, body, assigner_id=user.id)


@router.get("", response_model=list[AssignmentOut])
async def list_all(
    session: SessionDep,
    user: CurrentUser,
    plan_id: int | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
):
    return await assignments.list_assignments(session, plan_id, assignee_id, status)


@router.put("/{assignment_id}", response_model=AssignmentOut)
async def update(
    assignment_id: int, body: AssignmentUpdate, session: SessionDep, user: CurrentUser
):
    return await assignments.update_assignment(session, assignment_id, body)
```

- [ ] **Step 6: Wire router into `app/main.py`** — add `assignments` to the import and `app.include_router(assignments.router)`.

- [ ] **Step 7: Implement the two MCP tools in `app/mcp_server/server.py`**

First, REMOVE `"list_assignments"` and `"assign_test"` from the `_DEFERRED` list (leaving 11 deferred). Then add `from app.services import assignments` to the imports and add these two real tools (place them in the "Phase 1: entity-backed tools" region, before the deferred section):

```python
@mcp.tool()
async def assign_test(
    case_id: int,
    plan_id: int,
    assignee_id: int,
    assignee_type: str,
    deadline: str | None = None,
) -> dict:
    """Assign a test case (in a plan) to a human or agent. assignee_type: human|agent."""
    import datetime as _dt

    parsed_deadline = _dt.datetime.fromisoformat(deadline) if deadline else None
    async with _session() as s:
        from app.schemas.assignment import AssignmentCreate

        a = await assignments.create_assignment(
            s,
            AssignmentCreate(
                case_id=case_id, plan_id=plan_id, assignee_id=assignee_id,
                assignee_type=assignee_type, deadline=parsed_deadline,
            ),
            assigner_id=None,  # MCP callers are agents; no human assigner
        )
        return {"id": a.id, "status": a.status, "assignee_id": a.assignee_id}


@mcp.tool()
async def list_assignments(
    plan_id: int | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    """List assignments, optionally filtered — agents poll this to discover work."""
    async with _session() as s:
        rows = await assignments.list_assignments(s, plan_id, assignee_id, status)
        return [
            {"id": a.id, "case_id": a.case_id, "plan_id": a.plan_id,
             "assignee_id": a.assignee_id, "assignee_type": a.assignee_type,
             "status": a.status}
            for a in rows
        ]
```

- [ ] **Step 8: Write the MCP test `tests/test_mcp_assignments.py`**

```python
import pytest

from app.mcp_server import server as mcp
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import plans, projects, suites, testcases


@pytest.fixture(autouse=True)
def _use_test_session(session, monkeypatch):
    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(mcp, "_session", lambda: _Ctx())


@pytest.mark.asyncio
async def test_assign_and_list_via_mcp(session, user):
    p = await projects.create_project(session, ProjectCreate(name="M", prefix="MAS"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))

    res = await mcp.assign_test(
        case_id=tc.id, plan_id=plan.id, assignee_id=user.id, assignee_type="agent"
    )
    assert res["status"] == "open"
    rows = await mcp.list_assignments(plan_id=plan.id)
    assert len(rows) == 1
    assert rows[0]["assignee_id"] == user.id
```

- [ ] **Step 9: Run tests + lint**

`.venv/bin/pytest tests/test_assignments.py tests/test_mcp_assignments.py -v` → all PASS; full suite green; ruff clean.

- [ ] **Step 10: Verify MCP tool count unchanged (still 19, but now 8 real / 11 stub)**

Run:
```bash
.venv/bin/python -c "
import asyncio
from app.mcp_server import server as mcp
tools = asyncio.run(mcp.mcp.list_tools())
print('tools:', len(tools))
assert len(tools) == 19, len(tools)
print('assign_test' in [t.name for t in tools], 'list_assignments' in [t.name for t in tools])
"
```
Expected: `tools: 19` and `True True`.

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "feat: assignments service + endpoints + MCP tools (assign_test, list_assignments)"
```
Trailer as above.

---

## Task 7: CLI verbs for plans / builds / milestones / assignments

Extend `cli/main.py` with the admin verbs for the new entities, following the existing `_request` pattern.

**Files:**
- Modify: `cli/main.py`
- Test: `tests/test_cli.py` (append)

- [ ] **Step 1: Append failing tests to `tests/test_cli.py`**

```python
def test_plan_create_invokes_post(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_request", lambda m, p, **k: calls.append((m, p, k)) or {"id": 1})
    result = runner.invoke(cli.app, ["plan", "create", "5", "--name", "Sprint"])
    assert result.exit_code == 0
    assert calls[0][0] == "POST"
    assert calls[0][1] == "/api/v1/projects/5/plans"
    assert calls[0][2]["json_body"]["name"] == "Sprint"


def test_build_create_invokes_post(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_request", lambda m, p, **k: calls.append((m, p, k)) or {"id": 2})
    result = runner.invoke(cli.app, ["build", "create", "7", "--name", "v1", "--commit", "abc"])
    assert result.exit_code == 0
    assert calls[0][1] == "/api/v1/plans/7/builds"
    assert calls[0][2]["json_body"]["commit_id"] == "abc"


def test_assign_create_invokes_post(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_request", lambda m, p, **k: calls.append((m, p, k)) or {"id": 3})
    result = runner.invoke(
        cli.app,
        ["assign", "create", "4", "--plan", "7", "--to", "9", "--type", "agent"],
    )
    assert result.exit_code == 0
    assert calls[0][1] == "/api/v1/assignments"
    assert calls[0][2]["json_body"]["assignee_id"] == 9
```

- [ ] **Step 2: Run it — verify failure**

- [ ] **Step 3: Append to `cli/main.py`**

Add new Typer sub-apps after the existing ones (near the top where `project_app` etc. are defined):
```python
plan_app = typer.Typer(help="Manage test plans")
build_app = typer.Typer(help="Manage builds")
milestone_app = typer.Typer(help="Manage milestones")
assign_app = typer.Typer(help="Manage assignments")
app.add_typer(plan_app, name="plan")
app.add_typer(build_app, name="build")
app.add_typer(milestone_app, name="milestone")
app.add_typer(assign_app, name="assign")
```
Then add the commands (after the existing command definitions, before `if __name__ == "__main__":`):
```python
@plan_app.command("create")
def plan_create(project_id: int, name: str = typer.Option(..., "--name")):
    _print(_request("POST", f"/api/v1/projects/{project_id}/plans", json_body={"name": name}))


@plan_app.command("list")
def plan_list(project_id: int):
    _print(_request("GET", f"/api/v1/projects/{project_id}/plans"))


@plan_app.command("add-case")
def plan_add_case(plan_id: int, case: int = typer.Option(..., "--case")):
    _print(_request("POST", f"/api/v1/plans/{plan_id}/cases", json_body={"case_ids": [case]}))


@build_app.command("create")
def build_create(
    plan_id: int,
    name: str = typer.Option(..., "--name"),
    tag: str = typer.Option(None, "--tag"),
    commit: str = typer.Option(None, "--commit"),
):
    body = {"name": name}
    if tag:
        body["tag"] = tag
    if commit:
        body["commit_id"] = commit
    _print(_request("POST", f"/api/v1/plans/{plan_id}/builds", json_body=body))


@build_app.command("list")
def build_list(plan_id: int):
    _print(_request("GET", f"/api/v1/plans/{plan_id}/builds"))


@milestone_app.command("create")
def milestone_create(plan_id: int, name: str = typer.Option(..., "--name")):
    _print(_request("POST", f"/api/v1/plans/{plan_id}/milestones", json_body={"name": name}))


@assign_app.command("create")
def assign_create(
    case_id: int,
    plan: int = typer.Option(..., "--plan"),
    to: int = typer.Option(..., "--to"),
    type_: str = typer.Option("human", "--type"),
):
    _print(
        _request(
            "POST", "/api/v1/assignments",
            json_body={
                "case_id": case_id, "plan_id": plan,
                "assignee_id": to, "assignee_type": type_,
            },
        )
    )


@assign_app.command("list")
def assign_list(plan: int = typer.Option(None, "--plan"), assignee: int = typer.Option(None, "--assignee")):
    params = {}
    if plan is not None:
        params["plan_id"] = plan
    if assignee is not None:
        params["assignee_id"] = assignee
    _print(_request("GET", "/api/v1/assignments", params=params))
```

- [ ] **Step 4: Run tests + lint** — `tests/test_cli.py` all PASS; full suite green; ruff clean (add `# noqa: B008` only if ruff flags a `typer.Option` Path default — none here, so likely no noqa needed).

- [ ] **Step 5: Smoke-test** — `.venv/bin/agentqa plan --help` and `.venv/bin/agentqa assign --help` show the new verbs, no traceback.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: CLI verbs for plans, builds, milestones, assignments"
```
Trailer as above.

---

## Task 8: Update Dogfood to Use the Plan/Build API + Final Verification

Prove the gap is closed: `scripts/dogfood.py` no longer creates the plan via ORM — it uses the new `plans`/`builds` services (the public surface). Then run full verification.

**Files:**
- Modify: `scripts/dogfood.py`
- Test: full suite + live E2E

- [ ] **Step 1: Replace the ORM plan creation in `scripts/dogfood.py`**

Change `_get_or_create_plan` to use the `plans` service instead of constructing `TestPlan` directly. Replace the function body so it calls the service (find-or-create by listing then creating):
```python
async def _get_or_create_plan(session: AsyncSession, project_id: int):
    from app.schemas.plan import PlanCreate
    from app.services import plans

    for existing in await plans.list_plans(session, project_id):
        if existing.name == PLAN_NAME:
            return existing
    return await plans.create_plan(session, project_id, PlanCreate(name=PLAN_NAME))
```
Update the module docstring: remove the "created via ORM directly" caveat and note the plan is now created via the public `plans` service (the Phase 2a gap is closed). Remove the now-unused `from app.models.plan import TestPlan` import if nothing else uses it.

- [ ] **Step 2: Re-run dogfood end-to-end**

```bash
.venv/bin/pytest --junitxml=dogfood-results.xml -q
.venv/bin/python -m scripts.dogfood
```
Expected: prints the catalog summary (9 suites, 45 cases, executions recorded), no errors, plan created via the service.

- [ ] **Step 3: Full suite + lint + MCP tool count**

```bash
.venv/bin/pytest -q                       # all pass
.venv/bin/ruff check app/ cli/ scripts/ tests/
.venv/bin/ruff format --check app/ cli/ scripts/ tests/
```
Expected: all green; both ruff gates clean.

- [ ] **Step 4: Live E2E — create a plan + build + assignment via REST**

```bash
.venv/bin/uvicorn app.main:app --port 8012 >/tmp/aq3.log 2>&1 &
# (login as admin/admin, get key) then:
#   POST /api/v1/projects/{id}/plans        -> plan
#   POST /api/v1/plans/{plan}/builds         -> build
#   POST /api/v1/plans/{plan}/cases          -> link a case
#   POST /api/v1/assignments                 -> assignment
# confirm each returns 201, then kill uvicorn
```
Expected: every call returns 201/200 — the full plan/build/assignment surface works over HTTP.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: dogfood uses public plan API; close Phase 2a plan/build gap"
```
Trailer as above.

---

## Phase 2a Done — What Exists

- Public service + REST for platforms, test plans (+ case/platform links), builds (find-or-create), milestones, assignments
- MCP: `assign_test` + `list_assignments` implemented (19 tools total: 8 real, 11 deferred)
- CLI: plan/build/milestone/assign verbs
- Dogfood now records runs entirely through the public surface (no ORM workaround)

## Deferred to Phase 2b

Evidence/provenance: persist execution claims + reasoning, artifacts → MinIO, claim verification, audit reports; pgvector embeddings + `get_failure_context` / `search_similar_failures`; requirements + traceability; `get_agent_execution_history`, `get_coverage_gaps`, `create_requirement`, the remaining MCP stubs.

---

## Self-Review

**Spec coverage:** plans ✓, builds ✓ (find-or-create agrees with execution upsert), milestones ✓, plan-case links ✓, platforms ✓, assignments ✓ (REST + 2 MCP tools), CLI ✓, dogfood-via-API ✓.
**Type consistency:** services return ORM objects; schemas use `from_attributes`; `add_cases(session, plan_id, case_ids, platform_id, urgency)` signature matches REST `add_cases` and the test calls; `create_build` find-or-create matches `executions._upsert_build` semantics; MCP `assign_test`/`list_assignments` names match the removed `_DEFERRED` entries so the tool count stays 19.
**No placeholders:** every step has full code or exact commands.
