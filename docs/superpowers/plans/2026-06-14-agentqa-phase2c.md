# AgentQA Phase 2c — Embeddings & Self-Correction

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the self-*correction* loop — generate semantic embeddings of execution reasoning/notes, store them in pgvector, and expose `search_similar_failures` (find failures that mean the same thing across cases) and `get_failure_context` (an agent pulls its own prior failure evidence + similar failures before fixing something).

**Architecture:** Continues the established pattern (transport-agnostic services, REST + MCP, savepoint-isolated tests). Embeddings come from a local sentence-transformers model (all-MiniLM-L6-v2, 384-dim) behind a thin `app/embeddings.py` seam: `embed(text) -> list[float]`. The model + torch live in an OPTIONAL `[embeddings]` extra (lazy-loaded; a clear error if absent) so the base install and Docker image stay lean. The 384-dim vector is stored on `execution_reasoning.embedding` (pgvector `Vector(384)`), generated at record time. Similarity is `embedding <=> query` (cosine distance) via pgvector. Unit tests monkeypatch `embeddings.embed` with a deterministic fake, so the pgvector column + cosine queries are exercised for real against the test DB while the suite never needs torch.

**Tech Stack:** Same as before + `pgvector.sqlalchemy.Vector` (the `pgvector` package is already a dependency) + optional `sentence-transformers` (`[embeddings]` extra).

**Context — why this phase:** Phase 2b stores claims, reasoning, and artifacts (the *measurement* + evidence loop). Phase 2c adds *retrieval*: an agent that just failed a test can call `get_failure_context` to see its prior reasoning on that test plus semantically similar failures elsewhere — the input to actually self-correcting. This implements the last 2 of the original 4 deferred MCP tools tied to evidence; requirements/traceability (`get_coverage_gaps`, `create_requirement`) remain for Phase 2d.

**Key invariant to preserve:** embedding generation must be OPTIONAL at runtime — if the `[embeddings]` extra isn't installed, recording an execution must still succeed (just without an embedding). `embed()` is only called when the model is available; failures to embed never break a run.

---

## File Structure

```
app/embeddings.py          # lazy sentence-transformers; embed(text)->list[float]; EMBEDDING_DIM=384;  (new)
                           # is_available() guard
app/models/evidence.py     # ExecutionReasoning gains embedding: Vector(384) column                    (modify)
app/services/evidence.py   # record_claims_and_reasoning embeds notes+reasoning (best-effort);          (modify)
                           # search_similar_failures, get_failure_context
app/schemas/evidence.py    # SimilarFailure, FailureContext, FailureExecution                           (modify)
app/api/evidence.py        # GET /cases/{id}/failure-context, GET /cases/{id}/similar-failures          (modify)
app/mcp_server/server.py   # implement get_failure_context + search_similar_failures (stubs 4->2)        (modify)
cli/main.py                # context failure / context similar verbs                                     (modify)
pyproject.toml             # add [embeddings] optional extra (sentence-transformers)                     (modify)
migrations/versions/...    # add execution_reasoning.embedding vector(384) column                        (new)
tests/conftest.py          # CREATE EXTENSION vector on test DB before create_all                        (modify)
tests/_embed_helpers.py    # deterministic fake_embed(text)->384 floats for tests                        (new)
tests/test_embeddings.py, test_similar_failures.py, test_failure_context.py, test_mcp_failure.py        (new)
```

**Design notes:**
- `execution_reasoning.embedding` is nullable — most rows (no reasoning/notes, or embeddings extra absent) have NULL; similarity queries filter `embedding IS NOT NULL`.
- `record_claims_and_reasoning` gains a `notes` param; the embedded text is `notes + " " + json.dumps(reasoning)` (whichever parts exist). Embedding is best-effort: wrapped so a missing model / encode error never fails the run (logged-and-skipped).
- The test DB (created via `create_all`, not migrations) needs the `vector` extension; conftest must `CREATE EXTENSION IF NOT EXISTS vector` before `create_all`, or the `Vector` column DDL fails.

---

## Task 1: Embeddings Module + pgvector Column + Migration + Test Harness

**Files:**
- Create: `app/embeddings.py`, `tests/_embed_helpers.py`
- Modify: `pyproject.toml`, `app/models/evidence.py`, `tests/conftest.py`
- Create: a new Alembic migration
- Test: `tests/test_embeddings.py`

- [ ] **Step 1: Add the `[embeddings]` optional extra to `pyproject.toml`**

Under `[project.optional-dependencies]` (which already has `dev = [...]`), add:
```toml
embeddings = [
    "sentence-transformers>=3.0",
]
```
Do NOT install it in this session (keeps torch out of the venv); the unit tests monkeypatch `embed`. Reinstall the base only if needed: `.venv/bin/pip install -e ".[dev]" -q`.

- [ ] **Step 2: Write `app/embeddings.py`**

```python
"""Local sentence-transformers embeddings (optional [embeddings] extra).

embed() lazy-loads all-MiniLM-L6-v2 on first use. If the extra isn't installed,
is_available() returns False and callers skip embedding (runs still succeed).
Tests monkeypatch `embed` directly, so the model is never loaded in CI.
"""
from functools import lru_cache

EMBEDDING_DIM = 384
_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer  # heavy import, lazy

    return SentenceTransformer(_MODEL_NAME)


def is_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


def embed(text: str) -> list[float]:
    """Return a normalized EMBEDDING_DIM vector. Raises if the extra is absent."""
    vec = _model().encode(text, normalize_embeddings=True)
    return vec.tolist()
```

- [ ] **Step 3: Add the `embedding` column to `ExecutionReasoning` in `app/models/evidence.py`**

Add the import at the top: `from pgvector.sqlalchemy import Vector`. In the `ExecutionReasoning` class, add (after `token_count`):
```python
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
```

- [ ] **Step 4: Update `tests/conftest.py` so the test DB has the vector extension**

In the `engine` fixture, the `async with eng.begin() as conn:` block must create the extension BEFORE `create_all` (the `Vector` column DDL needs the type). Change it to:
```python
    eng = create_async_engine(TEST_DB_URL)
    async with eng.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
```
(`text` is already imported in conftest.)

- [ ] **Step 5: Write `tests/_embed_helpers.py`**

```python
"""Deterministic fake embedding for tests — identical text -> identical vector,
so similarity ordering is predictable without loading a real model."""
import hashlib
import math

DIM = 384


def fake_embed(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode()).digest()
    vals = [((digest[i % len(digest)] + i * 7) % 256) / 255.0 for i in range(DIM)]
    norm = math.sqrt(sum(v * v for v in vals)) or 1.0
    return [v / norm for v in vals]
```

- [ ] **Step 6: Write the failing test `tests/test_embeddings.py`**

```python
import pytest

from app import embeddings
from tests._embed_helpers import fake_embed


def test_fake_embed_is_deterministic_and_dim():
    a = fake_embed("login failed")
    b = fake_embed("login failed")
    c = fake_embed("payment failed")
    assert len(a) == embeddings.EMBEDDING_DIM
    assert a == b
    assert a != c


def test_embed_module_has_contract():
    # embed + is_available exist; we don't load the real model here.
    assert hasattr(embeddings, "embed")
    assert callable(embeddings.embed)
    assert isinstance(embeddings.is_available(), bool)


@pytest.mark.skipif(True, reason="integration: requires [embeddings] extra (torch)")
def test_real_embed_dim():
    v = embeddings.embed("hello world")
    assert len(v) == embeddings.EMBEDDING_DIM
```

- [ ] **Step 7: Run it — verify pass** (`.venv/bin/pytest tests/test_embeddings.py -v` → 2 pass, 1 skip)

- [ ] **Step 8: Generate the migration**

```bash
.venv/bin/alembic revision -m "add execution_reasoning embedding vector column"
```
Open the generated file and fill in (add `import sqlalchemy as sa` and `from pgvector.sqlalchemy import Vector` at the top if not present):
```python
def upgrade() -> None:
    op.add_column(
        "execution_reasoning",
        sa.Column("embedding", Vector(384), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("execution_reasoning", "embedding")
```
Confirm `down_revision` points at the previous head (the Phase 1 review-fix migration `13de60bfa83f`).

- [ ] **Step 9: Apply it + verify**

```bash
.venv/bin/alembic upgrade head
docker compose exec -T postgres psql -U agentqa -c "\d execution_reasoning" | grep embedding
```
Expected: an `embedding | vector(384)` column.

- [ ] **Step 10: Run full suite + lint**

`.venv/bin/pytest -q` → all pass (98 → 100: 2 new embedding tests; the new column doesn't break existing tests since it's nullable and conftest now creates the extension). `.venv/bin/ruff check app/ cli/ scripts/ tests/` + `format --check` clean.

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "feat: embeddings module + pgvector column + migration + test harness"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## Task 2: Generate Embeddings at Record Time (best-effort)

**Files:**
- Modify: `app/services/evidence.py`, `app/services/executions.py`
- Test: `tests/test_embeddings.py` (append)

- [ ] **Step 1: Append the failing test to `tests/test_embeddings.py`**

```python
import json

from sqlalchemy import select

from app import embeddings as emb_mod
from app.models.evidence import ExecutionReasoning
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
async def test_embedding_stored_when_available(session, monkeypatch):
    monkeypatch.setattr(emb_mod, "is_available", lambda: True)
    monkeypatch.setattr(emb_mod, "embed", fake_embed)
    tc, plan = await _fixture(session, "EMB1")
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id, plan_id=plan.id, build_name="b", status="fail",
            notes="assertion error on login", reasoning={"trace": "line 12"},
        ),
        tester_id=None,
    )
    row = (
        await session.execute(
            select(ExecutionReasoning).where(ExecutionReasoning.execution_id == ex.id)
        )
    ).scalar_one()
    assert row.embedding is not None
    # the embedding equals fake_embed of the combined text
    expected = fake_embed("assertion error on login " + json.dumps({"trace": "line 12"}))
    assert list(row.embedding) == pytest.approx(expected, rel=1e-5)


@pytest.mark.asyncio
async def test_record_succeeds_when_embeddings_unavailable(session, monkeypatch):
    monkeypatch.setattr(emb_mod, "is_available", lambda: False)
    tc, plan = await _fixture(session, "EMB2")
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id, plan_id=plan.id, build_name="b", status="fail",
            notes="some failure", reasoning={"x": 1},
        ),
        tester_id=None,
    )
    row = (
        await session.execute(
            select(ExecutionReasoning).where(ExecutionReasoning.execution_id == ex.id)
        )
    ).scalar_one()
    assert row.embedding is None  # gracefully skipped
```

- [ ] **Step 2: Run it — verify failure**

- [ ] **Step 3: Update `record_claims_and_reasoning` in `app/services/evidence.py`**

Add `import json` and `from app import embeddings` at the top. Change the signature to accept `notes` and compute an embedding. Replace the function body so it builds the reasoning row (when reasoning/agent_model/notes present), computes a best-effort embedding, and attaches it:
```python
async def record_claims_and_reasoning(
    session: AsyncSession,
    execution_id: int,
    claims: list[str],
    reasoning: dict | None,
    agent_model: str | None,
    session_id: str | None,
    notes: str | None = None,
) -> None:
    """Persist claims + reasoning (+ best-effort embedding). Does NOT commit."""
    for claim_text in claims:
        session.add(ExecutionClaim(execution_id=execution_id, claim_text=claim_text))

    has_reasoning_row = reasoning is not None or agent_model is not None or bool(notes)
    if not has_reasoning_row:
        return

    embed_text = " ".join(
        part for part in [notes, json.dumps(reasoning) if reasoning is not None else None] if part
    ).strip()
    embedding = None
    if embed_text and embeddings.is_available():
        try:
            embedding = embeddings.embed(embed_text)
        except Exception:
            embedding = None  # best-effort: never fail a run on embedding errors

    session.add(
        ExecutionReasoning(
            execution_id=execution_id,
            reasoning=reasoning,
            agent_model=agent_model,
            agent_session_id=session_id,
            embedding=embedding,
        )
    )
```

- [ ] **Step 4: Pass `notes` from `record_execution`** in `app/services/executions.py`

Update the `record_claims_and_reasoning(...)` call to also pass `notes=data.notes`:
```python
    await record_claims_and_reasoning(
        session,
        execution.id,
        data.claims,
        data.reasoning,
        data.agent_model,
        data.session_id,
        notes=data.notes,
    )
```

- [ ] **Step 5: Run tests + lint** — new embedding tests pass; full suite green (100 → 102); ruff clean.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: best-effort embedding generation at execution record time"
```
Trailer as above.

---

## Task 3: search_similar_failures (pgvector cosine)

Find executions across OTHER cases whose reasoning embedding is closest to the target case's most recent embedded execution.

**Files:**
- Modify: `app/schemas/evidence.py`, `app/services/evidence.py`, `app/api/evidence.py`
- Test: `tests/test_similar_failures.py`

- [ ] **Step 1: Append schema to `app/schemas/evidence.py`**

```python
class SimilarFailure(BaseModel):
    execution_id: int
    case_id: int
    status: str
    distance: float
```

- [ ] **Step 2: Write the failing test `tests/test_similar_failures.py`**

```python
import pytest

from app import embeddings as emb_mod
from app.schemas.execution import ExecutionCreate
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import evidence, executions, plans, projects, suites, testcases
from tests._embed_helpers import fake_embed


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch):
    monkeypatch.setattr(emb_mod, "is_available", lambda: True)
    monkeypatch.setattr(emb_mod, "embed", fake_embed)


async def _case(session, prefix, name="c"):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name=name))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    return tc, plan


async def _fail(session, tc, plan, notes):
    return await executions.record_execution(
        session,
        ExecutionCreate(case_id=tc.id, plan_id=plan.id, build_name="b", status="fail", notes=notes),
        tester_id=None,
    )


@pytest.mark.asyncio
async def test_similar_failures_finds_matching_reasoning(session):
    a_tc, a_plan = await _case(session, "SF1", "a")
    b_tc, b_plan = await _case(session, "SF2", "b")
    c_tc, c_plan = await _case(session, "SF3", "c")
    await _fail(session, a_tc, a_plan, "null pointer in auth handler")
    await _fail(session, b_tc, b_plan, "null pointer in auth handler")  # identical -> nearest
    await _fail(session, c_tc, c_plan, "totally unrelated timeout error")

    results = await evidence.search_similar_failures(session, a_tc.id, n=5)
    assert len(results) >= 1
    # nearest is case B (identical reasoning text -> distance ~0), not C
    assert results[0].case_id == b_tc.id
    assert results[0].distance < 0.01
    # the target case itself is excluded
    assert all(r.case_id != a_tc.id for r in results)


@pytest.mark.asyncio
async def test_similar_failures_empty_when_no_embedding(session):
    a_tc, a_plan = await _case(session, "SF4", "a")
    # a failure with NO notes/reasoning -> no embedding -> nothing to match on
    await executions.record_execution(
        session,
        ExecutionCreate(case_id=a_tc.id, plan_id=a_plan.id, build_name="b", status="fail"),
        tester_id=None,
    )
    assert await evidence.search_similar_failures(session, a_tc.id) == []
```

- [ ] **Step 3: Run it — verify failure**

- [ ] **Step 4: Append to `app/services/evidence.py`**

Add `from app.schemas.evidence import SimilarFailure` to imports. Then:
```python
async def search_similar_failures(
    session: AsyncSession, case_id: int, n: int = 5
) -> list[SimilarFailure]:
    # query vector = most recent embedded execution for this case
    q = (
        select(ExecutionReasoning.embedding)
        .select_from(ExecutionReasoning)
        .join(Execution, Execution.id == ExecutionReasoning.execution_id)
        .join(TestCaseVersion, TestCaseVersion.id == Execution.version_id)
        .where(
            TestCaseVersion.case_id == case_id,
            ExecutionReasoning.embedding.is_not(None),
        )
        .order_by(Execution.created_at.desc())
        .limit(1)
    )
    query_vec = (await session.execute(q)).scalars().first()
    if query_vec is None:
        return []

    distance = ExecutionReasoning.embedding.cosine_distance(query_vec)
    stmt = (
        select(
            Execution.id, TestCaseVersion.case_id, Execution.status, distance.label("distance")
        )
        .select_from(ExecutionReasoning)
        .join(Execution, Execution.id == ExecutionReasoning.execution_id)
        .join(TestCaseVersion, TestCaseVersion.id == Execution.version_id)
        .where(
            ExecutionReasoning.embedding.is_not(None),
            TestCaseVersion.case_id != case_id,
        )
        .order_by(distance)
        .limit(n)
    )
    rows = (await session.execute(stmt)).all()
    return [
        SimilarFailure(
            execution_id=r.id, case_id=r.case_id, status=r.status, distance=float(r.distance)
        )
        for r in rows
    ]
```

- [ ] **Step 5: Append route to `app/api/evidence.py`**

Add `SimilarFailure` to the schema imports. Then:
```python
@router.get("/cases/{case_id}/similar-failures", response_model=list[SimilarFailure])
async def similar_failures(
    case_id: int, session: SessionDep, user: CurrentUser, n: int = 5
):
    return await evidence.search_similar_failures(session, case_id, n)
```

- [ ] **Step 6: Run tests + lint** — `tests/test_similar_failures.py` 2 pass; full suite green; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: search_similar_failures via pgvector cosine distance"
```
Trailer as above.

---

## Task 4: get_failure_context (self-correction bundle)

The bundle an agent reads before fixing: the case's recent failures (with step-level failures + notes), prior reasoning, artifacts, and semantically similar failures.

**Files:**
- Modify: `app/schemas/evidence.py`, `app/services/evidence.py`, `app/api/evidence.py`
- Test: `tests/test_failure_context.py`

- [ ] **Step 1: Append schemas to `app/schemas/evidence.py`**

```python
class StepFailure(BaseModel):
    step_id: int
    status: str
    notes: str | None = None


class FailureExecution(BaseModel):
    execution_id: int
    status: str
    notes: str | None = None
    step_failures: list[StepFailure] = []


class FailureContext(BaseModel):
    case_id: int
    case_name: str
    recent_executions: list[FailureExecution] = []
    prior_reasoning: list[dict] = []
    artifacts: list[ArtifactOut] = []
    similar_failures: list[SimilarFailure] = []
```

- [ ] **Step 2: Write the failing test `tests/test_failure_context.py`**

```python
import pytest

from app import embeddings as emb_mod
from app import storage
from app.schemas.execution import ExecutionCreate, StepResultIn
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import StepIn, TestCaseCreate
from app.services import evidence, executions, plans, projects, suites, testcases
from app.services.errors import NotFound
from tests._embed_helpers import fake_embed


@pytest.fixture(autouse=True)
def _fakes(monkeypatch):
    monkeypatch.setattr(emb_mod, "is_available", lambda: True)
    monkeypatch.setattr(emb_mod, "embed", fake_embed)
    monkeypatch.setattr(storage, "put_object", lambda key, data, ct: key)


@pytest.mark.asyncio
async def test_failure_context_bundle(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="FC1"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(
        session, s.id, TestCaseCreate(name="login", steps=[StepIn(action="submit")])
    )
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id, plan_id=plan.id, build_name="b", status="fail",
            notes="auth blew up", reasoning={"trace": "NPE"},
            step_results=[StepResultIn(step_number=1, status="fail", notes="500")],
        ),
        tester_id=None,
    )
    await evidence.upload_artifact(session, ex.id, "log", "l", b"x", "text/plain")

    ctx = await evidence.get_failure_context(session, tc.id)
    assert ctx.case_id == tc.id
    assert ctx.case_name == "login"
    assert len(ctx.recent_executions) == 1
    assert ctx.recent_executions[0].step_failures[0].status == "fail"
    assert ctx.prior_reasoning == [{"trace": "NPE"}]
    assert len(ctx.artifacts) == 1


@pytest.mark.asyncio
async def test_failure_context_unknown_case(session):
    with pytest.raises(NotFound):
        await evidence.get_failure_context(session, 999999)
```

- [ ] **Step 3: Run it — verify failure**

- [ ] **Step 4: Append to `app/services/evidence.py`**

Add imports: `from app.models.execution import ExecutionStep` and `from app.schemas.evidence import FailureContext, FailureExecution, StepFailure`. Then:
```python
async def get_failure_context(
    session: AsyncSession, case_id: int, plan_id: int | None = None, last_n: int = 5
) -> FailureContext:
    case = await session.get(TestCase, case_id)
    if case is None:
        raise NotFound(f"test case {case_id} not found")
    version_ids = (
        await session.execute(
            select(TestCaseVersion.id).where(TestCaseVersion.case_id == case_id)
        )
    ).scalars().all()

    ctx = FailureContext(case_id=case_id, case_name=case.name)
    if not version_ids:
        return ctx

    exec_stmt = (
        select(Execution)
        .where(Execution.version_id.in_(version_ids))
        .order_by(Execution.created_at.desc())
        .limit(last_n)
    )
    if plan_id is not None:
        exec_stmt = exec_stmt.where(Execution.plan_id == plan_id)
    exec_rows = list((await session.execute(exec_stmt)).scalars().all())

    for ex in exec_rows:
        step_fail_rows = (
            await session.execute(
                select(ExecutionStep)
                .where(
                    ExecutionStep.execution_id == ex.id,
                    ExecutionStep.status.in_(["fail", "blocked"]),
                )
                .order_by(ExecutionStep.id)
            )
        ).scalars().all()
        ctx.recent_executions.append(
            FailureExecution(
                execution_id=ex.id,
                status=ex.status,
                notes=ex.notes,
                step_failures=[
                    StepFailure(step_id=sf.step_id, status=sf.status, notes=sf.notes)
                    for sf in step_fail_rows
                ],
            )
        )
        for art in await list_artifacts(session, ex.id):
            ctx.artifacts.append(ArtifactOut.model_validate(art))

    reasoning_rows = (
        await session.execute(
            select(ExecutionReasoning.reasoning)
            .join(Execution, Execution.id == ExecutionReasoning.execution_id)
            .where(
                Execution.version_id.in_(version_ids),
                ExecutionReasoning.reasoning.is_not(None),
            )
            .order_by(Execution.created_at.desc())
            .limit(last_n)
        )
    ).scalars().all()
    ctx.prior_reasoning = [r for r in reasoning_rows if r is not None]

    ctx.similar_failures = await search_similar_failures(session, case_id, n=last_n)
    return ctx
```

- [ ] **Step 5: Append route to `app/api/evidence.py`**

Add `FailureContext` to schema imports. Then:
```python
@router.get("/cases/{case_id}/failure-context", response_model=FailureContext)
async def failure_context(
    case_id: int, session: SessionDep, user: CurrentUser,
    plan_id: int | None = None, last_n: int = 5,
):
    return await evidence.get_failure_context(session, case_id, plan_id, last_n)
```

- [ ] **Step 6: Run tests + lint** — `tests/test_failure_context.py` 2 pass; full suite green; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: get_failure_context self-correction bundle"
```
Trailer as above.

---

## Task 5: MCP Tools + CLI + Final Verification

**Files:**
- Modify: `app/mcp_server/server.py`, `cli/main.py`
- Test: `tests/test_mcp_failure.py`, `tests/test_cli.py` (append)

- [ ] **Step 1: Write the failing MCP test `tests/test_mcp_failure.py`**

```python
import pytest

from app import embeddings as emb_mod
from app.mcp_server import server as mcp
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import plans, projects, suites, testcases
from tests._embed_helpers import fake_embed


@pytest.fixture(autouse=True)
def _setup(session, monkeypatch):
    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(mcp, "_session", lambda: _Ctx())
    monkeypatch.setattr(emb_mod, "is_available", lambda: True)
    monkeypatch.setattr(emb_mod, "embed", fake_embed)


async def _case_plan(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="M", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(session, s.id, TestCaseCreate(name="c"))
    plan = await plans.create_plan(session, p.id, PlanCreate(name="Plan"))
    return tc, plan


@pytest.mark.asyncio
async def test_failure_context_via_mcp(session):
    tc, plan = await _case_plan(session, "MFC1")
    await mcp.record_test_run(
        case_id=tc.id, plan_id=plan.id, build_name="b", status="fail",
        notes="kaboom", reasoning={"t": "x"},
    )
    ctx = await mcp.get_failure_context(case_id=tc.id)
    assert ctx["case_id"] == tc.id
    assert len(ctx["recent_executions"]) == 1


@pytest.mark.asyncio
async def test_similar_failures_via_mcp(session):
    a_tc, a_plan = await _case_plan(session, "MFC2")
    b_tc, b_plan = await _case_plan(session, "MFC3")
    for tc, plan in [(a_tc, a_plan), (b_tc, b_plan)]:
        await mcp.record_test_run(
            case_id=tc.id, plan_id=plan.id, build_name="b", status="fail", notes="same boom"
        )
    res = await mcp.search_similar_failures(case_id=a_tc.id)
    assert any(r["case_id"] == b_tc.id for r in res)
```

- [ ] **Step 2: Run it — verify failure**

- [ ] **Step 3: Implement the 2 tools in `app/mcp_server/server.py`**

REMOVE `"get_failure_context"` and `"search_similar_failures"` from `_DEFERRED` (leaving exactly 2: `get_coverage_gaps`, `create_requirement`). Add real tools (in the entity-backed region):
```python
@mcp.tool()
async def get_failure_context(
    case_id: int, plan_id: int | None = None, last_n: int = 5
) -> dict:
    """Self-correction bundle: a case's recent failures, step failures, reasoning,
    artifacts, and semantically similar failures elsewhere."""
    async with _session() as s:
        ctx = await evidence.get_failure_context(s, case_id, plan_id, last_n)
        return ctx.model_dump(mode="json")


@mcp.tool()
async def search_similar_failures(case_id: int, n: int = 5) -> list[dict]:
    """Find failures across other cases whose reasoning is semantically closest."""
    async with _session() as s:
        rows = await evidence.search_similar_failures(s, case_id, n)
        return [r.model_dump() for r in rows]
```

- [ ] **Step 4: Append CLI verbs to `cli/main.py`**

Add a `context_app`:
```python
context_app = typer.Typer(help="Self-correction context")
app.add_typer(context_app, name="context")


@context_app.command("failure")
def context_failure(case_id: int, plan: int = typer.Option(None, "--plan")):
    params = {"plan_id": plan} if plan is not None else None
    _print(_request("GET", f"/api/v1/cases/{case_id}/failure-context", params=params))


@context_app.command("similar")
def context_similar(case_id: int, n: int = typer.Option(5, "--n")):
    _print(_request("GET", f"/api/v1/cases/{case_id}/similar-failures", params={"n": n}))
```
Add a CLI test to `tests/test_cli.py`:
```python
def test_context_failure_invokes_get(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_request", lambda m, p, **k: calls.append((m, p, k)) or {})
    result = runner.invoke(cli.app, ["context", "failure", "7"])
    assert result.exit_code == 0
    assert calls[0][1] == "/api/v1/cases/7/failure-context"
```

- [ ] **Step 5: Run tests + lint** — mcp_failure + cli tests pass; full suite green; ruff clean across `app/ cli/ scripts/ tests/`.

- [ ] **Step 6: Verify MCP tool count (19 total, 17 real / 2 stub)**

```bash
.venv/bin/python -c "
import asyncio
from app.mcp_server import server as mcp
names = [t.name for t in asyncio.run(mcp.mcp.list_tools())]
print('tools:', len(names))
assert len(names) == 19, len(names)
for n in ['get_failure_context','search_similar_failures']:
    assert n in names, n
remaining = {'get_coverage_gaps','create_requirement'} & set(names)
print('stubs left:', sorted(remaining))
assert remaining == {'get_coverage_gaps','create_requirement'}
print('OK')
"
```
Expected: `tools: 19`, `stubs left: ['create_requirement', 'get_coverage_gaps']`, `OK`.

- [ ] **Step 7: MCP smoke** — `timeout 2 .venv/bin/python -m app.mcp_server.server || true` (no traceback).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: MCP get_failure_context + search_similar_failures + CLI context verbs"
```
Trailer as above.

---

## Phase 2c Done — What Exists

- Local sentence-transformers embeddings (optional `[embeddings]` extra), generated best-effort at record time, stored in `execution_reasoning.embedding` (pgvector `Vector(384)`)
- `search_similar_failures` (cosine nearest across other cases) + `get_failure_context` (recent failures + step failures + reasoning + artifacts + similar failures)
- REST + MCP + CLI surfaces; MCP now 19 tools, 17 real / 2 stub (`get_coverage_gaps`, `create_requirement` → Phase 2d)

## Deferred to Phase 2d / 3

- 2d: requirements + traceability, `get_coverage_gaps`, `create_requirement`
- 3: Next.js supervision UI

---

## Self-Review

**Spec coverage:** embedding column + generation ✓, `search_similar_failures` (pgvector cosine) ✓, `get_failure_context` bundle (recent execs + step failures + reasoning + artifacts + similar) ✓ matches the design's stated return shape, 2 MCP tools ✓ (stubs 4→2), CLI ✓.
**Type consistency:** `record_claims_and_reasoning(..., notes=None)` new param matches the `record_execution` call passing `notes=data.notes`; `embed(text)->list[float]` + `is_available()->bool` consistent across module, fake, and call sites; `search_similar_failures(session, case_id, n)` signature matches REST/MCP/`get_failure_context` callers; `SimilarFailure`/`FailureContext`/`FailureExecution`/`StepFailure` schemas consistent across service returns and response_models; `embedding` column is `Vector(384)` everywhere (model, migration, EMBEDDING_DIM).
**No placeholders:** every step has full code or exact commands. Embeddings are best-effort (never fail a run); tests monkeypatch `embed` so torch is never needed; the real-model test is skip-guarded; conftest creates the `vector` extension so the test DB supports the column + cosine queries.
