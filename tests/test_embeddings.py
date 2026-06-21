import pytest
from sqlalchemy import select

from app import embeddings
from app import embeddings as emb_mod
from app.models.evidence import ExecutionReasoning
from app.schemas.execution import ExecutionCreate
from app.schemas.plan import PlanCreate
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import TestCaseCreate
from app.services import executions, plans, projects, suites, testcases
from tests._embed_helpers import fake_embed


def test_fake_embed_is_deterministic_and_dim():
    a = fake_embed("login failed")
    b = fake_embed("login failed")
    c = fake_embed("payment failed")
    assert len(a) == embeddings.EMBEDDING_DIM
    assert a == b
    assert a != c


def test_embed_text_drops_noise_keys_keeps_prose():
    # L33T-shape: commit/verdict/evidence_tail are noise; the prose is the signal
    r = {
        "commit": "be09f050abc",
        "method": "noVNC reconnect storm; UseBlacklist regressed",
        "verdict": "fail",
        "evidence_tail": "## long markdown dump\nstatus messaging ...",
    }
    out = embeddings.embed_text_for(r, None)
    assert "noVNC reconnect storm" in out
    assert "be09f050abc" not in out          # commit hash dropped
    assert "long markdown dump" not in out    # evidence_tail dropped
    assert "fail" not in out                  # verdict dropped


def test_embed_text_keeps_root_cause_shape():
    assert embeddings.embed_text_for({"root_cause": "int truncation drops cents"}, None) == (
        "int truncation drops cents"
    )


def test_embed_text_prepends_notes():
    assert embeddings.embed_text_for({"root_cause": "db timeout"}, "assertion failed") == (
        "assertion failed db timeout"
    )


def test_embed_text_none_reasoning_uses_notes():
    assert embeddings.embed_text_for(None, "just notes") == "just notes"


def test_embed_text_empty_when_only_noise():
    assert embeddings.embed_text_for({"commit": "x", "verdict": "fail"}, None) == ""


def test_embed_module_has_contract():
    # embed + is_available exist; we don't load the real model here.
    assert hasattr(embeddings, "embed")
    assert callable(embeddings.embed)
    assert isinstance(embeddings.is_available(), bool)


@pytest.mark.skipif(True, reason="integration: requires [embeddings] extra (torch)")
def test_real_embed_dim():
    v = embeddings.embed("hello world")
    assert len(v) == embeddings.EMBEDDING_DIM


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
            case_id=tc.id,
            plan_id=plan.id,
            build_name="b",
            status="fail",
            notes="assertion error on login",
            reasoning={"trace": "line 12"},
        ),
        tester_id=None,
    )
    row = (
        await session.execute(
            select(ExecutionReasoning).where(ExecutionReasoning.execution_id == ex.id)
        )
    ).scalar_one()
    assert row.embedding is not None
    # the embedding equals fake_embed of the cleaned text (notes + prose values,
    # no json.dumps scaffolding)
    expected = fake_embed("assertion error on login line 12")
    assert list(row.embedding) == pytest.approx(expected, rel=1e-5)


@pytest.mark.asyncio
async def test_record_succeeds_when_embeddings_unavailable(session, monkeypatch):
    monkeypatch.setattr(emb_mod, "is_available", lambda: False)
    tc, plan = await _fixture(session, "EMB2")
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id,
            plan_id=plan.id,
            build_name="b",
            status="fail",
            notes="some failure",
            reasoning={"x": 1},
        ),
        tester_id=None,
    )
    row = (
        await session.execute(
            select(ExecutionReasoning).where(ExecutionReasoning.execution_id == ex.id)
        )
    ).scalar_one()
    assert row.embedding is None  # gracefully skipped
