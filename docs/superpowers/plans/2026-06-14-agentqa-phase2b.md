# AgentQA Phase 2b — Evidence & Provenance

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn AgentQA from a pass/fail ledger into an evidence store — persist the claims and reasoning an agent makes when it records a run, store binary artifacts (traces/logs/screenshots) in MinIO, let other agents verify claims and file audit reports, and expose a single evidence bundle per test case.

**Architecture:** Continues the Phase 1/2a pattern: transport-agnostic async services (`app/services/evidence.py`) raising domain errors, thin FastAPI routers, Pydantic `from_attributes` schemas, MCP tools wrapping services, Typer CLI verbs. Binary blobs live in MinIO behind a thin `app/storage.py` module (the `minio` SDK); structured records (claims, verifications, reasoning, audit reports, artifact metadata) live in Postgres. All evidence tables already exist from the Phase 1 schema migration — **no new migration required**.

**Tech Stack:** Same as before + the `minio` Python SDK (added to `pyproject.toml`). MinIO is already in `docker-compose.yml` (ports 9000/9001, `minioadmin`/`minioadmin`, bucket `agentqa-artifacts`).

**Context — why this phase:** Phase 2a closed the plan/build gap so runs can be recorded fully via the API. Phase 2b adds the *reasoning* layer the user asked for ("why did it fail / evidence of claims / verify off-band"): claims + reasoning + artifacts + adversarial verification. Embeddings/`get_failure_context`/`search_similar_failures` are deferred to Phase 2c; requirements/traceability to Phase 2d.

**Testability principle:** `app/storage.py` exposes module-level functions that the service calls by attribute (`storage.put_object(...)`). Unit tests monkeypatch those functions so the suite never needs a live MinIO. One real-MinIO integration test is marked and skipped when MinIO is unreachable.

---

## File Structure

```
app/storage.py            # MinIO client: ensure_bucket(), put_object(key,data,ct)->key, get_object(key)->bytes  (new)
app/schemas/evidence.py   # ClaimIn, ReasoningIn, ArtifactOut, ClaimOut, VerificationCreate,                     (new)
                          # VerificationOut, AuditReportCreate, AuditReportOut, EvidenceBundle
app/services/evidence.py  # record_claims_and_reasoning (helper), upload_artifact, list_artifacts,              (new)
                          # list_unverified_claims, verify_claim, create_audit_report,
                          # evaluate_test_case, get_execution_evidence, get_agent_execution_history
app/api/evidence.py       # REST: executions/{id}/artifacts, claims, /claims/{id}/verify, /audit-reports, etc.  (new)
app/schemas/execution.py  # extend ExecutionCreate with claims[], reasoning, agent_model                         (modify)
app/services/executions.py# record_execution persists claims + reasoning                                         (modify)
app/mcp_server/server.py  # record_test_run passes claims/reasoning; implement 7 deferred tools                  (modify)
app/main.py               # include evidence router                                                              (modify)
cli/main.py               # artifact/claim/evidence verbs                                                        (modify)
pyproject.toml            # add minio dep                                                                        (modify)
tests/test_storage.py, test_evidence_claims.py, test_evidence_artifacts.py,
tests/test_evidence_verify.py, test_evidence_bundle.py, test_mcp_evidence.py                                     (new)
```

**Design notes:**
- `record_claims_and_reasoning(session, execution_id, claims, reasoning, agent_model, session_id)` is a service helper called by BOTH `record_execution` (so claims arrive with the run) and reusable later. It does not commit — the caller's transaction owns the commit.
- `upload_artifact` writes the blob via `storage.put_object` FIRST, then inserts the `execution_artifacts` row with the returned key. Blob key format: `exec/{execution_id}/{artifact_type}/{uuid4hex}-{safe_title}`.
- `claim_verifications` is its own table → multiple auditors can verify the same claim independently (adversarial model). `list_unverified_claims` returns claims with zero verifications.
- MCP after this phase: 19 tools, **15 real / 4 stubs** (remaining stubs: `get_failure_context`, `search_similar_failures` → 2c; `get_coverage_gaps`, `create_requirement` → 2d).

---

## Task 1: MinIO Storage Module

**Files:**
- Create: `app/storage.py`
- Modify: `pyproject.toml`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Add `minio` to `pyproject.toml`** dependencies list (after `pgvector>=0.3.6`):

```toml
    "minio>=7.2",
```
Then reinstall: `.venv/bin/pip install -e ".[dev]" -q`.

- [ ] **Step 2: Write the failing test `tests/test_storage.py`**

These tests verify the key-building + content-type plumbing WITHOUT a live MinIO by monkeypatching the client. An additional integration test is skipped unless MinIO is reachable.

```python
import io

import pytest

from app import storage


def test_build_key_is_namespaced_and_safe():
    key = storage.build_key(execution_id=7, artifact_type="log", title="My Trace #1.txt")
    assert key.startswith("exec/7/log/")
    assert " " not in key and "#" not in key
    assert key.endswith("my-trace-1.txt")


def test_put_object_calls_client(monkeypatch):
    calls = {}

    class FakeClient:
        def bucket_exists(self, bucket):
            return True

        def make_bucket(self, bucket):
            calls["made"] = bucket

        def put_object(self, bucket, key, data, length, content_type):
            calls.update(bucket=bucket, key=key, length=length, content_type=content_type)

    monkeypatch.setattr(storage, "_client", lambda: FakeClient())
    returned = storage.put_object("exec/1/log/x.txt", b"hello", "text/plain")
    assert returned == "exec/1/log/x.txt"
    assert calls["bucket"] == storage._settings.s3_bucket
    assert calls["length"] == 5
    assert calls["content_type"] == "text/plain"


@pytest.mark.skipif(
    True, reason="integration: requires live MinIO; flip to False to run locally"
)
def test_roundtrip_against_real_minio():
    storage.ensure_bucket()
    key = storage.put_object("exec/test/log/it.txt", b"roundtrip", "text/plain")
    assert storage.get_object(key) == b"roundtrip"
```

- [ ] **Step 3: Run it — verify failure** (`.venv/bin/pytest tests/test_storage.py -v`)

- [ ] **Step 4: Write `app/storage.py`**

```python
"""Thin MinIO blob storage wrapper.

Service code calls the module-level functions (put_object/get_object); unit tests
monkeypatch `_client` so no live MinIO is needed. Bucket auto-created on first use.
"""
import io
import re
import uuid

from minio import Minio

from app.config import get_settings

_settings = get_settings()


def _client() -> Minio:
    endpoint = _settings.s3_endpoint.replace("http://", "").replace("https://", "")
    secure = _settings.s3_endpoint.startswith("https://")
    return Minio(
        endpoint,
        access_key=_settings.s3_access_key,
        secret_key=_settings.s3_secret_key,
        secure=secure,
    )


def ensure_bucket() -> None:
    client = _client()
    if not client.bucket_exists(_settings.s3_bucket):
        client.make_bucket(_settings.s3_bucket)


def _slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    return text.strip("-") or "artifact"


def build_key(execution_id: int, artifact_type: str, title: str) -> str:
    return f"exec/{execution_id}/{artifact_type}/{uuid.uuid4().hex[:8]}-{_slug(title)}"


def put_object(key: str, data: bytes, content_type: str) -> str:
    client = _client()
    if not client.bucket_exists(_settings.s3_bucket):
        client.make_bucket(_settings.s3_bucket)
    client.put_object(
        _settings.s3_bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
    )
    return key


def get_object(key: str) -> bytes:
    client = _client()
    response = client.get_object(_settings.s3_bucket, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
```

- [ ] **Step 5: Run tests + lint** — `tests/test_storage.py` 2 pass + 1 skipped; full suite green (was 75 → 77); ruff clean across `app/ cli/ scripts/ tests/`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: minio storage module (key building, put/get, bucket bootstrap)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## Task 2: Persist Claims + Reasoning on Executions

Extend the execution write path so an agent's claims and reasoning are stored when a run is recorded.

**Files:**
- Modify: `app/schemas/execution.py`, `app/services/executions.py`
- Create: `app/services/evidence.py` (the `record_claims_and_reasoning` helper lives here)
- Test: `tests/test_evidence_claims.py`

- [ ] **Step 1: Extend `app/schemas/execution.py`**

Add these fields to the existing `ExecutionCreate` model (keep all current fields):
```python
    claims: list[str] = []
    reasoning: dict | None = None
    agent_model: str | None = None
```

- [ ] **Step 2: Write the failing test `tests/test_evidence_claims.py`**

```python
import pytest
from sqlalchemy import select

from app.models.evidence import ExecutionClaim, ExecutionReasoning
from app.schemas.execution import ExecutionCreate
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import executions, plans, projects, suites, testcases


async def _fixture(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    return tc, plan


@pytest.mark.asyncio
async def test_record_execution_persists_claims_and_reasoning(session):
    tc, plan = await _fixture(session, "EV1")
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id, plan_id=plan.id, build_name="b", status="fail",
            claims=["login rejects bad password", "no 500 on empty body"],
            reasoning={"steps": ["checked status code", "inspected body"]},
            agent_model="claude-sonnet-4-6",
            session_id="sess-1",
        ),
        tester_id=None,
    )
    claims = (
        await session.execute(
            select(ExecutionClaim).where(ExecutionClaim.execution_id == ex.id)
        )
    ).scalars().all()
    assert {c.claim_text for c in claims} == {
        "login rejects bad password", "no 500 on empty body"
    }
    reasoning = (
        await session.execute(
            select(ExecutionReasoning).where(ExecutionReasoning.execution_id == ex.id)
        )
    ).scalar_one()
    assert reasoning.agent_model == "claude-sonnet-4-6"
    assert reasoning.agent_session_id == "sess-1"


@pytest.mark.asyncio
async def test_record_execution_without_claims_is_fine(session):
    tc, plan = await _fixture(session, "EV2")
    ex = await executions.record_execution(
        session,
        ExecutionCreate(case_id=tc.id, plan_id=plan.id, build_name="b", status="pass"),
        tester_id=None,
    )
    claims = (
        await session.execute(
            select(ExecutionClaim).where(ExecutionClaim.execution_id == ex.id)
        )
    ).scalars().all()
    assert claims == []
```

- [ ] **Step 3: Run it — verify failure**

- [ ] **Step 4: Create `app/services/evidence.py`** with the helper (more functions added in later tasks)

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import ExecutionClaim, ExecutionReasoning


async def record_claims_and_reasoning(
    session: AsyncSession,
    execution_id: int,
    claims: list[str],
    reasoning: dict | None,
    agent_model: str | None,
    session_id: str | None,
) -> None:
    """Persist claims + reasoning for an execution. Does NOT commit (caller owns tx)."""
    for claim_text in claims:
        session.add(ExecutionClaim(execution_id=execution_id, claim_text=claim_text))
    if reasoning is not None or agent_model is not None:
        session.add(
            ExecutionReasoning(
                execution_id=execution_id,
                reasoning=reasoning,
                agent_model=agent_model,
                agent_session_id=session_id,
            )
        )
```

- [ ] **Step 5: Wire into `app/services/executions.py`**

In `record_execution`, after the execution is flushed and step results are added, but BEFORE the final `await session.commit()`, add:
```python
    from app.services.evidence import record_claims_and_reasoning

    await record_claims_and_reasoning(
        session,
        execution.id,
        data.claims,
        data.reasoning,
        data.agent_model,
        data.session_id,
    )
```
(Place the import at the top of the file with the other imports if you prefer; a local import avoids any circular-import risk since evidence.py imports nothing from executions.py — either is fine, but top-level is cleaner. Verify no circular import.)

- [ ] **Step 6: Run tests + lint** — `tests/test_evidence_claims.py` 2 pass; full suite green; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: persist execution claims + reasoning on record"
```
Trailer as above.

---

## Task 3: Artifacts → MinIO

Upload a binary artifact for an execution: blob to MinIO, metadata row in Postgres.

**Files:**
- Create: `app/schemas/evidence.py`, `app/api/evidence.py`
- Modify: `app/services/evidence.py`, `app/main.py`
- Test: `tests/test_evidence_artifacts.py`

- [ ] **Step 1: Create `app/schemas/evidence.py`** (other schemas appended in later tasks)

```python
import datetime as dt

from pydantic import BaseModel


class ArtifactOut(BaseModel):
    id: int
    execution_id: int
    artifact_type: str
    title: str | None = None
    blob_key: str
    size: int | None = None
    mime_type: str | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Write the failing test `tests/test_evidence_artifacts.py`**

Storage is monkeypatched so no live MinIO is needed.

```python
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
        session, ex.id, artifact_type="log", title="run log",
        content=b"trace bytes", mime_type="text/plain",
    )
    assert art.id is not None
    assert art.blob_key.startswith(f"exec/{ex.id}/log/")
    assert art.size == len(b"trace bytes")
    # blob was handed to storage
    assert _fake_storage[art.blob_key][0] == b"trace bytes"
    # row persisted
    rows = (
        await session.execute(
            select(ExecutionArtifact).where(ExecutionArtifact.execution_id == ex.id)
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_list_artifacts(session, _fake_storage):
    ex = await _execution(session, "AR2")
    await evidence.upload_artifact(
        session, ex.id, "log", "a", b"x", "text/plain"
    )
    await evidence.upload_artifact(
        session, ex.id, "screenshot", "b", b"y", "image/png"
    )
    rows = await evidence.list_artifacts(session, ex.id)
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_upload_artifact_endpoint(client, auth_headers, session, _fake_storage):
    ex = await _execution(session, "ARE")
    resp = await client.post(
        f"/api/v1/executions/{ex.id}/artifacts",
        json={"artifact_type": "log", "title": "t", "content": "aGVsbG8=", "mime_type": "text/plain"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["artifact_type"] == "log"
```

NOTE: the endpoint accepts base64 `content` (`aGVsbG8=` == b"hello") so binary survives JSON. The service takes raw bytes; the router base64-decodes.

- [ ] **Step 3: Run it — verify failure**

- [ ] **Step 4: Append to `app/services/evidence.py`**

Add imports at top: `from sqlalchemy import select`, `from app import storage`, `from app.models.evidence import ExecutionArtifact`, `from app.models.execution import Execution`, `from app.services.errors import NotFound`. Then:

```python
async def _get_execution(session: AsyncSession, execution_id: int) -> Execution:
    ex = await session.get(Execution, execution_id)
    if ex is None:
        raise NotFound(f"execution {execution_id} not found")
    return ex


async def upload_artifact(
    session: AsyncSession,
    execution_id: int,
    artifact_type: str,
    title: str | None,
    content: bytes,
    mime_type: str | None,
) -> ExecutionArtifact:
    await _get_execution(session, execution_id)
    key = storage.build_key(execution_id, artifact_type, title or artifact_type)
    storage.put_object(key, content, mime_type or "application/octet-stream")
    artifact = ExecutionArtifact(
        execution_id=execution_id,
        artifact_type=artifact_type,
        title=title,
        blob_key=key,
        size=len(content),
        mime_type=mime_type,
    )
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)
    return artifact


async def list_artifacts(session: AsyncSession, execution_id: int) -> list[ExecutionArtifact]:
    stmt = (
        select(ExecutionArtifact)
        .where(ExecutionArtifact.execution_id == execution_id)
        .order_by(ExecutionArtifact.id)
    )
    return list((await session.execute(stmt)).scalars().all())
```

- [ ] **Step 5: Create `app/api/evidence.py`**

```python
import base64

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.schemas.evidence import ArtifactOut
from app.services import evidence

router = APIRouter(prefix="/api/v1", tags=["evidence"])


class _ArtifactIn(BaseModel):
    artifact_type: str
    title: str | None = None
    content: str  # base64-encoded bytes
    mime_type: str | None = None


@router.post(
    "/executions/{execution_id}/artifacts",
    response_model=ArtifactOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_artifact(
    execution_id: int, body: _ArtifactIn, session: SessionDep, user: CurrentUser
):
    content = base64.b64decode(body.content)
    return await evidence.upload_artifact(
        session, execution_id, body.artifact_type, body.title, content, body.mime_type
    )


@router.get("/executions/{execution_id}/artifacts", response_model=list[ArtifactOut])
async def list_artifacts(execution_id: int, session: SessionDep, user: CurrentUser):
    return await evidence.list_artifacts(session, execution_id)
```

- [ ] **Step 6: Wire router into `app/main.py`** — add `evidence` to the import and `app.include_router(evidence.router)`.

- [ ] **Step 7: Run tests + lint** — `tests/test_evidence_artifacts.py` 3 pass; full suite green; ruff clean.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: artifact upload to MinIO + metadata + endpoints"
```
Trailer as above.

---

## Task 4: Claim Verification (adversarial)

List claims awaiting verification; submit a verdict. Multiple auditors per claim.

**Files:**
- Modify: `app/schemas/evidence.py`, `app/services/evidence.py`, `app/api/evidence.py`
- Test: `tests/test_evidence_verify.py`

- [ ] **Step 1: Append schemas to `app/schemas/evidence.py`**

```python
class ClaimOut(BaseModel):
    id: int
    execution_id: int
    claim_text: str
    created_at: dt.datetime
    verification_count: int = 0

    model_config = {"from_attributes": True}


class VerificationCreate(BaseModel):
    verdict: str  # confirmed|refuted|inconclusive
    reasoning: dict | None = None


class VerificationOut(BaseModel):
    id: int
    claim_id: int
    auditor_id: int
    verdict: str
    reasoning: dict | None = None
    created_at: dt.datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Write the failing test `tests/test_evidence_verify.py`**

```python
import pytest

from app.schemas.evidence import VerificationCreate
from app.schemas.execution import ExecutionCreate
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import evidence, executions, plans, projects, suites, testcases
from app.services.errors import NotFound


async def _execution_with_claim(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id, plan_id=plan.id, build_name="b", status="pass",
            claims=["it works"],
        ),
        tester_id=None,
    )
    return ex


@pytest.mark.asyncio
async def test_unverified_then_verified(session, user):
    ex = await _execution_with_claim(session, "VF1")
    unverified = await evidence.list_unverified_claims(session)
    assert len(unverified) == 1
    claim_id = unverified[0].id

    v = await evidence.verify_claim(
        session, claim_id, VerificationCreate(verdict="confirmed", reasoning={"why": "checked"}),
        auditor_id=user.id,
    )
    assert v.verdict == "confirmed"
    # claim no longer appears as unverified
    assert await evidence.list_unverified_claims(session) == []


@pytest.mark.asyncio
async def test_multiple_auditors_per_claim(session, user):
    ex = await _execution_with_claim(session, "VF2")
    claim_id = (await evidence.list_unverified_claims(session))[0].id
    await evidence.verify_claim(
        session, claim_id, VerificationCreate(verdict="confirmed"), auditor_id=user.id
    )
    await evidence.verify_claim(
        session, claim_id, VerificationCreate(verdict="refuted"), auditor_id=user.id
    )
    verifications = await evidence.list_verifications(session, claim_id)
    assert {v.verdict for v in verifications} == {"confirmed", "refuted"}


@pytest.mark.asyncio
async def test_verify_unknown_claim_raises(session, user):
    with pytest.raises(NotFound):
        await evidence.verify_claim(
            session, 999999, VerificationCreate(verdict="confirmed"), auditor_id=user.id
        )


@pytest.mark.asyncio
async def test_verify_endpoint(client, auth_headers, session, user):
    ex = await _execution_with_claim(session, "VFE")
    unv = await client.get("/api/v1/claims/unverified", headers=auth_headers)
    assert unv.status_code == 200
    claim_id = unv.json()[0]["id"]
    resp = await client.post(
        f"/api/v1/claims/{claim_id}/verify",
        json={"verdict": "confirmed"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["verdict"] == "confirmed"
```

- [ ] **Step 3: Run it — verify failure**

- [ ] **Step 4: Append to `app/services/evidence.py`**

Add imports: `from sqlalchemy import func`, and models `ExecutionClaim`, `ClaimVerification`. Then:

```python
async def list_unverified_claims(
    session: AsyncSession, project_id: int | None = None, plan_id: int | None = None
) -> list[ExecutionClaim]:
    """Claims with zero verifications. Optional project/plan scoping via executions."""
    verified_subq = select(ClaimVerification.claim_id).distinct()
    stmt = select(ExecutionClaim).where(ExecutionClaim.id.not_in(verified_subq))
    if project_id is not None or plan_id is not None:
        from app.models.execution import Execution

        stmt = stmt.join(Execution, Execution.id == ExecutionClaim.execution_id)
        if plan_id is not None:
            stmt = stmt.where(Execution.plan_id == plan_id)
        # project scoping resolves through the plan; left to plan_id for Phase 2b
    stmt = stmt.order_by(ExecutionClaim.id)
    return list((await session.execute(stmt)).scalars().all())


async def verify_claim(
    session: AsyncSession, claim_id: int, data, auditor_id: int
) -> ClaimVerification:
    claim = await session.get(ExecutionClaim, claim_id)
    if claim is None:
        raise NotFound(f"claim {claim_id} not found")
    verification = ClaimVerification(
        claim_id=claim_id,
        auditor_id=auditor_id,
        verdict=data.verdict,
        reasoning=data.reasoning,
    )
    session.add(verification)
    await session.commit()
    await session.refresh(verification)
    return verification


async def list_verifications(
    session: AsyncSession, claim_id: int
) -> list[ClaimVerification]:
    stmt = (
        select(ClaimVerification)
        .where(ClaimVerification.claim_id == claim_id)
        .order_by(ClaimVerification.id)
    )
    return list((await session.execute(stmt)).scalars().all())
```

- [ ] **Step 5: Append routes to `app/api/evidence.py`**

Add imports: `from app.schemas.evidence import ClaimOut, VerificationCreate, VerificationOut`. Then:

```python
@router.get("/claims/unverified", response_model=list[ClaimOut])
async def unverified_claims(
    session: SessionDep,
    user: CurrentUser,
    project_id: int | None = None,
    plan_id: int | None = None,
):
    return await evidence.list_unverified_claims(session, project_id, plan_id)


@router.post(
    "/claims/{claim_id}/verify",
    response_model=VerificationOut,
    status_code=status.HTTP_201_CREATED,
)
async def verify(claim_id: int, body: VerificationCreate, session: SessionDep, user: CurrentUser):
    return await evidence.verify_claim(session, claim_id, body, auditor_id=user.id)
```

- [ ] **Step 6: Run tests + lint** — `tests/test_evidence_verify.py` 4 pass; full suite green; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: claim verification (list unverified, verify, multi-auditor)"
```
Trailer as above.

---

## Task 5: Audit Reports + evaluate_test_case

Audit agents file structured reports against a case version / suite / plan, and fetch a case version for quality assessment.

**Files:**
- Modify: `app/schemas/evidence.py`, `app/services/evidence.py`, `app/api/evidence.py`
- Test: `tests/test_evidence_audit.py`

- [ ] **Step 1: Append schemas to `app/schemas/evidence.py`**

```python
class AuditReportCreate(BaseModel):
    entity_type: str  # case_version|suite|plan
    entity_id: int
    findings: dict | None = None
    quality_score: int | None = None


class AuditReportOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    auditor_id: int
    findings: dict | None = None
    quality_score: int | None = None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class CaseEvaluation(BaseModel):
    case_version_id: int
    version: int
    summary: str | None = None
    step_count: int
    execution_count: int
    last_status: str | None = None
```

- [ ] **Step 2: Write the failing test `tests/test_evidence_audit.py`**

```python
import pytest

from app.schemas.evidence import AuditReportCreate
from app.schemas.execution import ExecutionCreate
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import StepIn, TestCaseCreate
from app.services import evidence, executions, plans, projects, suites, testcases


async def _case(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(
        session, s.id, TestCaseCreate(name="c", steps=[StepIn(action="a")])
    )
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    return tc, plan


@pytest.mark.asyncio
async def test_create_audit_report(session, user):
    tc, plan = await _case(session, "AU1")
    full = await testcases.get_test_case(session, tc.id)
    report = await evidence.create_audit_report(
        session,
        AuditReportCreate(
            entity_type="case_version", entity_id=full.current_version.id,
            findings={"issue": "shallow assertion"}, quality_score=40,
        ),
        auditor_id=user.id,
    )
    assert report.id is not None
    assert report.quality_score == 40


@pytest.mark.asyncio
async def test_evaluate_test_case(session, user):
    tc, plan = await _case(session, "AU2")
    full = await testcases.get_test_case(session, tc.id)
    await executions.record_execution(
        session,
        ExecutionCreate(case_id=tc.id, plan_id=plan.id, build_name="b", status="pass"),
        tester_id=None,
    )
    ev = await evidence.evaluate_test_case(session, full.current_version.id)
    assert ev.step_count == 1
    assert ev.execution_count == 1
    assert ev.last_status == "pass"


@pytest.mark.asyncio
async def test_audit_report_endpoint(client, auth_headers, session, user):
    tc, plan = await _case(session, "AUE")
    full = await testcases.get_test_case(session, tc.id)
    resp = await client.post(
        "/api/v1/audit-reports",
        json={"entity_type": "case_version", "entity_id": full.current_version.id,
              "quality_score": 80},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["quality_score"] == 80
```

- [ ] **Step 3: Run it — verify failure**

- [ ] **Step 4: Append to `app/services/evidence.py`**

Add imports: models `AuditReport`, and `from app.models.testcase import TestCaseVersion, TestStep`, `from app.models.execution import Execution`, and `from app.schemas.evidence import CaseEvaluation`. Then:

```python
async def create_audit_report(
    session: AsyncSession, data, auditor_id: int
) -> AuditReport:
    report = AuditReport(
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        auditor_id=auditor_id,
        findings=data.findings,
        quality_score=data.quality_score,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def evaluate_test_case(session: AsyncSession, case_version_id: int) -> CaseEvaluation:
    version = await session.get(TestCaseVersion, case_version_id)
    if version is None:
        raise NotFound(f"test case version {case_version_id} not found")
    step_count = (
        await session.execute(
            select(func.count()).select_from(TestStep).where(
                TestStep.version_id == case_version_id
            )
        )
    ).scalar_one()
    exec_stmt = (
        select(Execution)
        .where(Execution.version_id == case_version_id)
        .order_by(Execution.created_at.desc())
    )
    executions_for_version = list((await session.execute(exec_stmt)).scalars().all())
    return CaseEvaluation(
        case_version_id=case_version_id,
        version=version.version,
        summary=version.summary,
        step_count=step_count,
        execution_count=len(executions_for_version),
        last_status=executions_for_version[0].status if executions_for_version else None,
    )
```

- [ ] **Step 5: Append routes to `app/api/evidence.py`**

Add imports: `from app.schemas.evidence import AuditReportCreate, AuditReportOut, CaseEvaluation`. Then:

```python
@router.post(
    "/audit-reports", response_model=AuditReportOut, status_code=status.HTTP_201_CREATED
)
async def create_audit_report(
    body: AuditReportCreate, session: SessionDep, user: CurrentUser
):
    return await evidence.create_audit_report(session, body, auditor_id=user.id)


@router.get("/case-versions/{case_version_id}/evaluation", response_model=CaseEvaluation)
async def evaluate(case_version_id: int, session: SessionDep, user: CurrentUser):
    return await evidence.evaluate_test_case(session, case_version_id)
```

- [ ] **Step 6: Run tests + lint** — `tests/test_evidence_audit.py` 3 pass; full suite green; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: audit reports + evaluate_test_case"
```
Trailer as above.

---

## Task 6: Evidence Bundle + Agent Execution History

A single read that returns everything about a test case's runs; and all executions by a given agent.

**Files:**
- Modify: `app/schemas/evidence.py`, `app/services/evidence.py`, `app/api/evidence.py`
- Test: `tests/test_evidence_bundle.py`

- [ ] **Step 1: Append schemas to `app/schemas/evidence.py`**

```python
class EvidenceExecution(BaseModel):
    id: int
    status: str
    build_id: int | None = None
    created_at: dt.datetime
    claims: list[str] = []
    artifacts: list[ArtifactOut] = []

    model_config = {"from_attributes": True}


class EvidenceBundle(BaseModel):
    case_id: int
    executions: list[EvidenceExecution] = []


class AgentExecutionOut(BaseModel):
    id: int
    version_id: int
    status: str
    plan_id: int | None = None
    build_id: int | None = None
    created_at: dt.datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Write the failing test `tests/test_evidence_bundle.py`**

```python
import pytest

from app import storage
from app.schemas.execution import ExecutionCreate
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import evidence, executions, plans, projects, suites, testcases


@pytest.fixture(autouse=True)
def _fake_storage(monkeypatch):
    monkeypatch.setattr(storage, "put_object", lambda key, data, ct: key)


async def _case_with_run(session, prefix, agent_id):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id, plan_id=plan.id, build_name="b", status="fail",
            claims=["claim A"],
        ),
        tester_id=agent_id,
    )
    return tc, ex


@pytest.mark.asyncio
async def test_get_execution_evidence_bundle(session, user):
    tc, ex = await _case_with_run(session, "EB1", user.id)
    await evidence.upload_artifact(session, ex.id, "log", "l", b"x", "text/plain")
    bundle = await evidence.get_execution_evidence(session, tc.id)
    assert bundle.case_id == tc.id
    assert len(bundle.executions) == 1
    e = bundle.executions[0]
    assert e.claims == ["claim A"]
    assert len(e.artifacts) == 1


@pytest.mark.asyncio
async def test_get_agent_execution_history(session, user):
    tc, ex = await _case_with_run(session, "EB2", user.id)
    rows = await evidence.get_agent_execution_history(session, user.id)
    assert len(rows) == 1
    assert rows[0].id == ex.id


@pytest.mark.asyncio
async def test_evidence_endpoint(client, auth_headers, session, user):
    tc, ex = await _case_with_run(session, "EBE", user.id)
    resp = await client.get(f"/api/v1/cases/{tc.id}/evidence", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["case_id"] == tc.id
```

- [ ] **Step 3: Run it — verify failure**

- [ ] **Step 4: Append to `app/services/evidence.py`**

Add imports: `from app.models.testcase import TestCase` and `from app.schemas.evidence import AgentExecutionOut, EvidenceBundle, EvidenceExecution, ArtifactOut`. Then:

```python
async def get_execution_evidence(session: AsyncSession, case_id: int) -> EvidenceBundle:
    case = await session.get(TestCase, case_id)
    if case is None:
        raise NotFound(f"test case {case_id} not found")
    version_ids = (
        await session.execute(
            select(TestCaseVersion.id).where(TestCaseVersion.case_id == case_id)
        )
    ).scalars().all()
    bundle = EvidenceBundle(case_id=case_id, executions=[])
    if not version_ids:
        return bundle
    exec_rows = (
        await session.execute(
            select(Execution)
            .where(Execution.version_id.in_(version_ids))
            .order_by(Execution.created_at.desc())
        )
    ).scalars().all()
    for ex in exec_rows:
        claim_texts = (
            await session.execute(
                select(ExecutionClaim.claim_text).where(
                    ExecutionClaim.execution_id == ex.id
                )
            )
        ).scalars().all()
        artifacts = await list_artifacts(session, ex.id)
        bundle.executions.append(
            EvidenceExecution(
                id=ex.id, status=ex.status, build_id=ex.build_id, created_at=ex.created_at,
                claims=list(claim_texts),
                artifacts=[ArtifactOut.model_validate(a) for a in artifacts],
            )
        )
    return bundle


async def get_agent_execution_history(
    session: AsyncSession, agent_id: int, project_id: int | None = None
) -> list[Execution]:
    stmt = select(Execution).where(Execution.tester_id == agent_id)
    if project_id is not None:
        stmt = stmt.join(
            TestCaseVersion, TestCaseVersion.id == Execution.version_id
        ).join(TestCase, TestCase.id == TestCaseVersion.case_id).where(
            TestCase.project_id == project_id
        )
    stmt = stmt.order_by(Execution.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())
```

- [ ] **Step 5: Append routes to `app/api/evidence.py`**

Add imports: `from app.schemas.evidence import AgentExecutionOut, EvidenceBundle`. Then:

```python
@router.get("/cases/{case_id}/evidence", response_model=EvidenceBundle)
async def case_evidence(case_id: int, session: SessionDep, user: CurrentUser):
    return await evidence.get_execution_evidence(session, case_id)


@router.get("/agents/{agent_id}/executions", response_model=list[AgentExecutionOut])
async def agent_history(
    agent_id: int, session: SessionDep, user: CurrentUser, project_id: int | None = None
):
    return await evidence.get_agent_execution_history(session, agent_id, project_id)
```

- [ ] **Step 6: Run tests + lint** — `tests/test_evidence_bundle.py` 3 pass; full suite green; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: evidence bundle + agent execution history"
```
Trailer as above.

---

## Task 7: MCP Tool Bodies + CLI + Final Verification

Implement the 7 deferred MCP tools, pass claims/reasoning through `record_test_run`, add CLI verbs, and verify the whole phase.

**Files:**
- Modify: `app/mcp_server/server.py`, `cli/main.py`
- Test: `tests/test_mcp_evidence.py`, `tests/test_cli.py` (append)

- [ ] **Step 1: Write the failing MCP test `tests/test_mcp_evidence.py`**

```python
import pytest

from app import storage
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
    monkeypatch.setattr(storage, "put_object", lambda key, data, ct: key)


async def _case_plan(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="M", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    return tc, plan


@pytest.mark.asyncio
async def test_record_run_with_claims_then_evidence(session):
    tc, plan = await _case_plan(session, "MEV1")
    run = await mcp.record_test_run(
        case_id=tc.id, plan_id=plan.id, build_name="b", status="fail",
        claims=["x broke"], reasoning={"note": "stacktrace"},
    )
    ev = await mcp.get_execution_evidence(case_id=tc.id)
    assert ev["case_id"] == tc.id
    assert ev["executions"][0]["claims"] == ["x broke"]


@pytest.mark.asyncio
async def test_verify_claim_via_mcp(session, user):
    tc, plan = await _case_plan(session, "MEV2")
    await mcp.record_test_run(
        case_id=tc.id, plan_id=plan.id, build_name="b", status="pass", claims=["ok"]
    )
    unverified = await mcp.list_unverified_claims()
    assert len(unverified) >= 1
    cid = unverified[0]["id"]
    res = await mcp.verify_claim(claim_id=cid, verdict="confirmed", auditor_id=user.id)
    assert res["verdict"] == "confirmed"


@pytest.mark.asyncio
async def test_upload_artifact_via_mcp(session):
    tc, plan = await _case_plan(session, "MEV3")
    run = await mcp.record_test_run(case_id=tc.id, plan_id=plan.id, build_name="b", status="fail")
    art = await mcp.upload_artifact(
        execution_id=run["id"], artifact_type="log", title="t", content_base64="aGk="
    )
    assert art["artifact_type"] == "log"
```

- [ ] **Step 2: Run it — verify failure**

- [ ] **Step 3: Update `record_test_run` in `app/mcp_server/server.py`** to accept and pass claims/reasoning

Add `claims: list[str] | None = None` and `reasoning: dict | None = None` params to `record_test_run`, and pass them into `ExecutionCreate(..., claims=claims or [], reasoning=reasoning)`. Keep all existing params.

- [ ] **Step 4: Implement the 7 tools in `app/mcp_server/server.py`**

REMOVE these from `_DEFERRED`: `get_agent_execution_history`, `get_execution_evidence`, `list_unverified_claims`, `verify_claim`, `evaluate_test_case`, `create_audit_report`, `upload_artifact` (leaving 4 stubs: `get_failure_context`, `search_similar_failures`, `get_coverage_gaps`, `create_requirement`). Add `from app.services import evidence` and `import base64`. Add real tools (place with the entity-backed tools):

```python
@mcp.tool()
async def upload_artifact(
    execution_id: int, artifact_type: str, title: str, content_base64: str,
    mime_type: str | None = None,
) -> dict:
    """Upload a base64-encoded artifact (trace/log/screenshot/dump) for an execution."""
    async with _session() as s:
        art = await evidence.upload_artifact(
            s, execution_id, artifact_type, title,
            base64.b64decode(content_base64), mime_type,
        )
        return {"id": art.id, "artifact_type": art.artifact_type, "blob_key": art.blob_key}


@mcp.tool()
async def list_unverified_claims(
    project_id: int | None = None, plan_id: int | None = None
) -> list[dict]:
    """Claims awaiting verification — audit agents poll this."""
    async with _session() as s:
        rows = await evidence.list_unverified_claims(s, project_id, plan_id)
        return [
            {"id": c.id, "execution_id": c.execution_id, "claim_text": c.claim_text}
            for c in rows
        ]


@mcp.tool()
async def verify_claim(
    claim_id: int, verdict: str, auditor_id: int, reasoning: dict | None = None
) -> dict:
    """Submit a verdict (confirmed|refuted|inconclusive) for a claim."""
    from app.schemas.evidence import VerificationCreate

    async with _session() as s:
        v = await evidence.verify_claim(
            s, claim_id, VerificationCreate(verdict=verdict, reasoning=reasoning),
            auditor_id=auditor_id,
        )
        return {"id": v.id, "claim_id": v.claim_id, "verdict": v.verdict}


@mcp.tool()
async def create_audit_report(
    entity_type: str, entity_id: int, auditor_id: int,
    findings: dict | None = None, quality_score: int | None = None,
) -> dict:
    """File an audit report against a case_version|suite|plan."""
    from app.schemas.evidence import AuditReportCreate

    async with _session() as s:
        r = await evidence.create_audit_report(
            s,
            AuditReportCreate(
                entity_type=entity_type, entity_id=entity_id,
                findings=findings, quality_score=quality_score,
            ),
            auditor_id=auditor_id,
        )
        return {"id": r.id, "entity_type": r.entity_type, "quality_score": r.quality_score}


@mcp.tool()
async def evaluate_test_case(case_version_id: int) -> dict:
    """Return a test case version's shape + execution stats for quality assessment."""
    async with _session() as s:
        ev = await evidence.evaluate_test_case(s, case_version_id)
        return ev.model_dump()


@mcp.tool()
async def get_execution_evidence(case_id: int) -> dict:
    """Full evidence bundle for a case: executions with claims + artifacts."""
    async with _session() as s:
        bundle = await evidence.get_execution_evidence(s, case_id)
        return bundle.model_dump(mode="json")


@mcp.tool()
async def get_agent_execution_history(agent_id: int, project_id: int | None = None) -> list[dict]:
    """All executions recorded by a given agent — supervision/pattern analysis."""
    async with _session() as s:
        rows = await evidence.get_agent_execution_history(s, agent_id, project_id)
        return [
            {"id": e.id, "version_id": e.version_id, "status": e.status,
             "plan_id": e.plan_id, "build_id": e.build_id}
            for e in rows
        ]
```

- [ ] **Step 5: Append CLI verbs to `cli/main.py`**

Add an `evidence_app` and a `claim_app` (or extend existing). Minimal set:
```python
evidence_app = typer.Typer(help="Evidence & artifacts")
claim_app = typer.Typer(help="Claims & verification")
app.add_typer(evidence_app, name="evidence")
app.add_typer(claim_app, name="claim")


@evidence_app.command("bundle")
def evidence_bundle(case_id: int):
    _print(_request("GET", f"/api/v1/cases/{case_id}/evidence"))


@claim_app.command("unverified")
def claim_unverified(plan: int = typer.Option(None, "--plan")):
    params = {"plan_id": plan} if plan is not None else None
    _print(_request("GET", "/api/v1/claims/unverified", params=params))


@claim_app.command("verify")
def claim_verify(claim_id: int, verdict: str = typer.Option(..., "--verdict")):
    _print(_request("POST", f"/api/v1/claims/{claim_id}/verify", json_body={"verdict": verdict}))
```
Add a CLI test to `tests/test_cli.py`:
```python
def test_claim_verify_invokes_post(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_request", lambda m, p, **k: calls.append((m, p, k)) or {"id": 1})
    result = runner.invoke(cli.app, ["claim", "verify", "5", "--verdict", "confirmed"])
    assert result.exit_code == 0
    assert calls[0][1] == "/api/v1/claims/5/verify"
    assert calls[0][2]["json_body"]["verdict"] == "confirmed"
```

- [ ] **Step 6: Run tests + lint** — `tests/test_mcp_evidence.py` + new CLI test pass; full suite green; ruff clean across `app/ cli/ scripts/ tests/`.

- [ ] **Step 7: Verify MCP tool count (19 total, 15 real / 4 stub)**

```bash
.venv/bin/python -c "
import asyncio
from app.mcp_server import server as mcp
names = [t.name for t in asyncio.run(mcp.mcp.list_tools())]
print('tools:', len(names))
assert len(names) == 19, len(names)
for n in ['upload_artifact','list_unverified_claims','verify_claim','create_audit_report',
          'evaluate_test_case','get_execution_evidence','get_agent_execution_history']:
    assert n in names, n
print('remaining stubs should be get_failure_context/search_similar_failures/get_coverage_gaps/create_requirement')
print('OK')
"
```
Expected: `tools: 19` and `OK`.

- [ ] **Step 8: MCP server smoke** — `timeout 2 .venv/bin/python -m app.mcp_server.server || true` (no traceback).

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: MCP evidence tools + record_test_run claims/reasoning + CLI verbs"
```
Trailer as above.

- [ ] **Step 10: Final live E2E** (controller may run): record a run with claims via REST → list unverified → verify → fetch case evidence bundle, all over HTTP returning 200/201.

---

## Phase 2b Done — What Exists

- Execution claims + reasoning persisted on record (REST + MCP `record_test_run`)
- Artifacts stored in MinIO via `app/storage.py` + metadata rows; upload via REST + MCP
- Claim verification (adversarial, multi-auditor) + audit reports + `evaluate_test_case`
- Evidence bundle per case + agent execution history (REST + MCP)
- MCP: 19 tools, 15 real / 4 deferred (`get_failure_context`, `search_similar_failures` → 2c; `get_coverage_gaps`, `create_requirement` → 2d)

## Deferred to Phase 2c / 2d

- 2c: pgvector embedding column on `execution_reasoning`, embedding generation, `get_failure_context`, `search_similar_failures`
- 2d: requirements + traceability, `get_coverage_gaps`, `create_requirement`

---

## Self-Review

**Spec coverage:** claims+reasoning persist ✓, artifacts→MinIO ✓, verify_claim/list_unverified ✓ (multi-auditor table), audit_reports ✓, evaluate_test_case ✓, evidence bundle ✓, agent history ✓, 7 MCP tools implemented ✓ (stubs 11→4), CLI ✓.
**Type consistency:** `record_claims_and_reasoning(session, execution_id, claims, reasoning, agent_model, session_id)` signature matches the executions call; `upload_artifact(session, execution_id, artifact_type, title, content, mime_type)` matches service + REST (base64-decoded) + MCP (base64 param); `verify_claim`/`create_audit_report` services take a data object + auditor_id, matching REST (user.id) and MCP (explicit auditor_id); `storage.put_object(key, data, content_type)` and `build_key(execution_id, artifact_type, title)` consistent across storage module, tests, and service.
**No placeholders:** every step has full code or exact commands. Storage is monkeypatched in unit tests; the one real-MinIO test is skip-guarded.
**Test-isolation note:** all evidence unit tests use the savepoint `session` fixture; artifact tests monkeypatch `storage.put_object` so no live MinIO is needed.
